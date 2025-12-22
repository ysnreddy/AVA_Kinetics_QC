import psycopg2
import pandas as pd
import logging
import json
import io
from typing import Dict, Any, Tuple
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from processing_pipeline.services.label_loader import load_cvat_labels

# -------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Dataset Generator
# -------------------------------------------------------------------
class DatasetGenerator:
    """
    Generates AVA-style CSV annotations from CVAT database data.
    Dynamically synchronized with the project's YAML label schema.
    """

    def __init__(self, db_params: Dict[str, Any], project_id: int):
        self.db_params = db_params
        self.project_id = project_id
        
        # 1. Load labels from YAML via the shared loader
        all_labels = load_cvat_labels()
        
        # 2. Extract the 'person' label schema
        person_label = next((l for l in all_labels if l["name"] == "person"), None)
        if not person_label:
            raise ValueError("Label configuration must contain a label named 'person'.")

        # 3. Build Attribute Definitions dynamically from the YAML content
        self.attribute_definitions = {
            attr["name"]: {"options": attr["values"]}
            for attr in person_label["attributes"]
        }

        # 4. Calculate Action ID mapping (deterministic order)
        self.action_id_map = self._calculate_action_mapping()

    def _calculate_action_mapping(self) -> Dict[str, int]:
        """
        Assigns a unique base action ID for each attribute group based on YAML order.
        Using sorted keys ensures IDs are consistent across different environments.
        """
        mapping = {}
        cumulative_count = 0

        for attr_name in sorted(self.attribute_definitions.keys()):
            mapping[attr_name] = cumulative_count
            cumulative_count += len(self.attribute_definitions[attr_name]["options"])

        return mapping

    def _get_db_connection(self):
        return psycopg2.connect(**self.db_params)

    def _fetch_data(self) -> pd.DataFrame:
        """
        Fetch approved and golden annotations for the given project.
        """
        try:
            conn = self._get_db_connection()

            approved_query = """
                SELECT a.keyframe_name, a.person_id,
                       a.xtl, a.ytl, a.xbr, a.ybr, a.attributes
                FROM annotations a
                JOIN tasks t ON a.task_id = t.task_id
                WHERE t.qc_status = 'approved'
                  AND t.project_id = %s
            """

            golden_query = """
                SELECT keyframe_name, person_id,
                       xtl, ytl, xbr, ybr, attributes
                FROM golden_annotations
                WHERE original_project_id = %s
            """

            approved_df = pd.read_sql(
                approved_query, conn, params=(self.project_id,)
            )
            golden_df = pd.read_sql(
                golden_query, conn, params=(self.project_id,)
            )

            conn.close()

            logger.info(
                f"Retrieved {len(approved_df)} approved and "
                f"{len(golden_df)} golden annotations."
            )

            return pd.concat([approved_df, golden_df], ignore_index=True)

        except Exception as exc:
            logger.error(f"Database query failed: {exc}")
            raise

    def generate_ava_csv_in_memory(
        self,
        manifest_data: Dict[str, Any],
        image_width: int = 1280,
        image_height: int = 720
    ) -> Tuple[str, int]:
        """
        Generate AVA-style CSV content in memory using dynamic Action IDs.
        """
        df = self._fetch_data()

        if df.empty:
            logger.warning("No approved or golden annotations found.")
            return "", 0

        ava_rows = []

        for _, row in df.iterrows():
            keyframe_name = row["keyframe_name"]
            origin = manifest_data.get(keyframe_name)

            if not origin:
                logger.warning(f"Missing manifest entry: {keyframe_name}")
                continue

            video_id = origin["source_video"].replace(".mp4", "")
            frame_timestamp = origin["source_frame"]

            # BBox Normalization (0.0 to 1.0)
            x1 = row["xtl"] / image_width
            y1 = row["ytl"] / image_height
            x2 = row["xbr"] / image_width
            y2 = row["ybr"] / image_height

            # Parse attributes from DB
            try:
                attributes = (
                    json.loads(row["attributes"])
                    if isinstance(row["attributes"], str)
                    else row["attributes"]
                )
                if not isinstance(attributes, dict):
                    raise ValueError
            except Exception:
                logger.warning(f"Skipping malformed attributes for {keyframe_name}")
                continue

            # Map attributes to AVA Action IDs
            for attr_name, attr_value in attributes.items():
                if attr_value is None:
                    continue

                base_id = self.action_id_map.get(attr_name)
                if base_id is None:
                    # Attribute exists in DB but not in our current YAML config
                    continue

                try:
                    # Get index from the dynamic options list
                    options_list = self.attribute_definitions[attr_name]["options"]
                    option_index = options_list.index(attr_value)

                    # AVA Logic: Action ID = Base + Index + 1 (AVA is 1-indexed)
                    action_id = base_id + option_index + 1

                    ava_rows.append([
                        video_id,
                        frame_timestamp,
                        f"{x1:.6f}",
                        f"{y1:.6f}",
                        f"{x2:.6f}",
                        f"{y2:.6f}",
                        action_id,
                        row["person_id"]
                    ])

                except ValueError:
                    logger.warning(
                        f"Value '{attr_value}' not found in schema for '{attr_name}'"
                    )

        columns = [
            "video_id", "frame_timestamp",
            "x1", "y1", "x2", "y2",
            "action_id", "person_id"
        ]

        ava_df = pd.DataFrame(ava_rows, columns=columns)
        
        # Sort for consistency
        ava_df.sort_values(
            by=["video_id", "frame_timestamp", "person_id"],
            inplace=True
        )

        buffer = io.StringIO()
        ava_df.to_csv(buffer, index=False)

        logger.info(
            f"AVA CSV generated with {len(ava_df)} rows (in-memory)."
        )

        return buffer.getvalue(), len(ava_df)