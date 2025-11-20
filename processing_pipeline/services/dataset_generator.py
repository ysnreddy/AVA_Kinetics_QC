import psycopg2
import pandas as pd
import logging
import json
from typing import Dict, Any
from tqdm import tqdm
from typing import Dict
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# This must match the label schema in your CVAT project
ATTRIBUTE_DEFINITIONS = {
    "ppe_helmet": {"options": ["helmet_worn", "no_helmet", "helmet_incorrect"]},
    "ppe_vest": {"options": ["vest_worn", "no_vest"]},
    "ppe_gloves": {"options": ["gloves_worn", "no_gloves"]},
    "ppe_boots": {"options": ["safety_boots_worn", "no_safety_boots"]},
    "work_activity": {
        "options": ["idle", "welding", "cutting", "climbing", "lifting_materials", "machine_operation", "supervising",
                    "walking"]},
    "posture_safety": {"options": ["upright_normal", "bending", "overreaching", "unsafe_posture"]},
    "hazard_proximity": {
        "options": ["safe_zone", "near_hot_surface", "near_heavy_load", "near_moving_machine", "near_open_edge"]},
    "team_interaction": {"options": ["working_alone", "pair_work", "small_team", "large_group", "supervisor_present"]},
}


def calculate_action_mapping() -> Dict[str, int]:
    """Assigns a unique starting integer ID for each attribute group."""
    mapping = {}
    cumulative_count = 0
    for attr_name in sorted(ATTRIBUTE_DEFINITIONS.keys()):
        mapping[attr_name] = cumulative_count
        cumulative_count += len(ATTRIBUTE_DEFINITIONS[attr_name]["options"])
    return mapping


class DatasetGenerator:
    def __init__(self, db_params: Dict[str, Any], manifest_path: str):
        self.db_params = db_params
        try:
            with open(manifest_path, 'r') as f:
                self.manifest_data = json.load(f)
            logger.info(f"✓ Manifest loaded successfully from {manifest_path}")
        except FileNotFoundError:
            logger.error(f"❌ Manifest file not found at: {manifest_path}")
            raise
        self.action_id_map = calculate_action_mapping()
        self.conn = None

    def connect_db(self):
        self.conn = psycopg2.connect(**self.db_params)

    def close_db(self):
        if self.conn:
            self.conn.close()

    def generate_ava_csv(self, output_path: str, image_width=1280, image_height=720):
        self.connect_db()
        if not self.conn:
            logger.error("Database connection failed. Aborting CSV generation.")
            return

        try:
            # Query 1: Get all 'approved' annotations (the 80% non-overlap)
            solo_query = """
                         SELECT a.keyframe_name, a.person_id, a.xtl, a.ytl, a.xbr, a.ybr, a.attributes
                         FROM annotations a
                                  JOIN tasks t ON a.task_id = t.task_id
                         WHERE t.qc_status = 'approved'; \
                         """
            solo_df = pd.read_sql(solo_query, self.conn)
            logger.info(f"Retrieved {len(solo_df)} 'approved' solo annotations.")

            # Query 2: Get all 'golden' annotations (the 20% overlap, adjudicated)
            golden_query = """
                           SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes
                           FROM golden_annotations; \
                           """
            golden_df = pd.read_sql(golden_query, self.conn)
            logger.info(f"Retrieved {len(golden_df)} 'golden' adjudicated annotations.")

            # Combine them into one master dataframe
            df = pd.concat([solo_df, golden_df], ignore_index=True)

            if df.empty:
                logger.warning("⚠️ No 'approved' or 'golden' annotations found. The output CSV will be empty.")
                df.to_csv(output_path, index=False)
                return

            logger.info(f"Processing a total of {len(df)} annotations for the final dataset.")

            ava_rows = []
            for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="Formatting AVA CSV"):
                keyframe_name = row["keyframe_name"]

                origin_data = self.manifest_data.get(keyframe_name)
                if not origin_data:
                    logger.warning(f"Could not find '{keyframe_name}' in manifest. Skipping annotation.")
                    continue

                video_id = origin_data["source_video"].replace('.mp4', '')
                frame_timestamp = origin_data["source_frame"]

                x1_norm = row["xtl"] / image_width
                y1_norm = row["ytl"] / image_height
                x2_norm = row["xbr"] / image_width
                y2_norm = row["ybr"] / image_height

                attributes = row["attributes"]
                person_id = row["person_id"]

                for attr_name, attr_value in attributes.items():
                    if attr_value is None: continue
                    base_id = self.action_id_map.get(attr_name)
                    if base_id is None: continue

                    try:
                        options_list = ATTRIBUTE_DEFINITIONS[attr_name]["options"]
                        option_index = options_list.index(attr_value)
                        final_action_id = base_id + option_index + 1

                        ava_rows.append([
                            video_id, frame_timestamp,
                            f"{x1_norm:.6f}", f"{y1_norm:.6f}", f"{x2_norm:.6f}", f"{y2_norm:.6f}",
                            final_action_id, person_id
                        ])
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping attribute '{attr_name}' with value '{attr_value}': {e}")

            header = ["video_id", "frame_timestamp", "x1", "y1", "x2", "y2", "action_id", "person_id"]
            ava_df = pd.DataFrame(ava_rows, columns=header)
            ava_df.sort_values(by=["video_id", "frame_timestamp", "person_id"], inplace=True)
            ava_df.to_csv(output_path, index=False)

            logger.info(f"✅ Successfully generated AVA-Kinetics dataset with {len(ava_df)} rows at: {output_path}")

        finally:
            self.close_db()