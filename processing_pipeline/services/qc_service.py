import psycopg2
import pandas as pd
from collections import defaultdict
from sklearn.metrics import cohen_kappa_score
import logging
import json # REQUIRED for parsing JSONB attributes
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class QCService:
    # FIX 1: Must accept project_id from the FastAPI router
    def __init__(self, db_params: Dict[str, Any], project_id: int):
        self.db_params = db_params
        self.project_id = project_id # Store project_id

    def _get_db_connection(self):
        return psycopg2.connect(**self.db_params)

    def _parse_attributes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Defensively parses attributes column from JSON string to Python dict."""
        def safe_load(attr):
            if isinstance(attr, str):
                try:
                    return json.loads(attr)
                except json.JSONDecodeError:
                    return {}
            return attr

        if 'attributes' in df.columns:
            df['attributes'] = df['attributes'].apply(safe_load)
        return df

    def _get_annotations_for_task(self, task_id):
        """Fetches all annotations for a given task, indexed by keyframe."""
        query = "SELECT keyframe_name, person_id, attributes FROM annotations WHERE task_id = %s"
        conn = self._get_db_connection()
        df = pd.read_sql(query, conn, params=(task_id,))
        conn.close()

        # FIX 2: Apply JSON parsing to annotations
        df = self._parse_attributes(df)

        annotations = defaultdict(dict)
        for _, row in df.iterrows():
            annotations[row['keyframe_name']][row['person_id']] = row['attributes']
        return annotations

    def _get_golden_annotations_for_frames(self, keyframe_names):
        """
        Fetches golden annotations for a list of keyframes, filtered by the current project.
        """
        # FIX 3: Query uses 'original_project_id' for filtering
        golden_query = """
            SELECT ga.keyframe_name, ga.person_id, ga.attributes 
            FROM golden_annotations ga
            WHERE ga.keyframe_name = ANY(%s) 
              AND ga.original_project_id = %s
        """
        conn = self._get_db_connection()
        # Pass keyframe list AND project_id
        df = pd.read_sql(golden_query, conn, params=(keyframe_names, self.project_id))
        conn.close()

        # FIX 4: Apply JSON parsing
        df = self._parse_attributes(df)

        annotations = defaultdict(dict)
        for _, row in df.iterrows():
            annotations[row['keyframe_name']][row['person_id']] = row['attributes']
        return annotations

    def calculate_kappa_vs_golden(self, task_id: int, attribute_names: list) -> Dict[str, float]:
        """
        Calculates Cohen's Kappa for a task's annotator vs. the Golden Set.
        """
        try:
            # 1. Get the annotator's work
            annotator_data = self._get_annotations_for_task(task_id)
            if not annotator_data:
                logger.warning(f"No annotations found for task {task_id}")
                return {attr: 0.0 for attr in attribute_names}

            # 2. Get the corresponding golden annotations (Filtered by Project ID)
            golden_data = self._get_golden_annotations_for_frames(list(annotator_data.keys()))
            if not golden_data:
                logger.warning(f"No golden annotations found for frames in task {task_id}")
                return {attr: 0.0 for attr in attribute_names}

            kappa_scores = {}
            for attr in attribute_names:
                labels_annotator = []
                labels_golden = []

                # 3. Alignment and Comparison
                for frame in golden_data.keys():
                    if frame not in annotator_data: continue

                    golden_persons = set(golden_data[frame].keys())
                    annotator_persons = set(annotator_data[frame].keys())
                    common_persons = golden_persons.intersection(annotator_persons)

                    for person_id in common_persons:
                        # Attributes are now safely dictionaries
                        label_a = annotator_data[frame][person_id].get(attr)
                        label_g = golden_data[frame][person_id].get(attr)

                        if label_a is not None and label_g is not None:
                            labels_annotator.append(label_a)
                            labels_golden.append(label_g)

                # 4. Calculate Kappa
                if len(labels_annotator) > 1:
                    try:
                        kappa = cohen_kappa_score(labels_annotator, labels_golden)
                        kappa_scores[attr] = 0.0 if pd.isna(kappa) else kappa
                    except ValueError as e:
                        logger.warning(f"Could not calculate kappa for {attr}: {e}")
                        kappa_scores[attr] = 0.0
                else:
                    kappa_scores[attr] = 1.0 if labels_annotator == labels_golden and len(labels_annotator) > 0 else 0.0

            return kappa_scores

        except Exception as e:
            logger.error(f"Error calculating kappa for task {task_id}: {e}")
            return {attr: 0.0 for attr in attribute_names}