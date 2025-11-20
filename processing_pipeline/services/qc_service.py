import psycopg2
import pandas as pd
from collections import defaultdict
from sklearn.metrics import cohen_kappa_score
import logging
from typing import Dict
logger = logging.getLogger(__name__)


class QCService:
    def __init__(self, db_params):
        self.db_params = db_params

    def _get_db_connection(self):
        return psycopg2.connect(**self.db_params)

    def _get_annotations_for_task(self, task_id):
        """Fetches all annotations for a given task, indexed by keyframe."""
        query = "SELECT keyframe_name, person_id, attributes FROM annotations WHERE task_id = %s"
        conn = self._get_db_connection()
        df = pd.read_sql(query, conn, params=(task_id,))
        conn.close()

        # Re-format into a dictionary for fast lookup: {keyframe: {person_id: attributes}}
        annotations = defaultdict(dict)
        for _, row in df.iterrows():
            annotations[row['keyframe_name']][row['person_id']] = row['attributes']
        return annotations

    def _get_golden_annotations_for_frames(self, keyframe_names):
        """Fetches golden annotations for a list of keyframes."""
        query = "SELECT keyframe_name, person_id, attributes FROM golden_annotations WHERE keyframe_name = ANY(%s)"
        conn = self._get_db_connection()
        df = pd.read_sql(query, conn, params=(keyframe_names,))
        conn.close()

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

            # 2. Get the corresponding golden annotations
            golden_data = self._get_golden_annotations_for_frames(list(annotator_data.keys()))
            if not golden_data:
                logger.warning(f"No golden annotations found for frames in task {task_id}")
                return {attr: 0.0 for attr in attribute_names}

            kappa_scores = {}
            for attr in attribute_names:
                labels_annotator = []
                labels_golden = []

                # 3. Align annotations
                for frame in golden_data.keys():
                    if frame not in annotator_data: continue

                    # Compare annotations for person_ids present in BOTH sets
                    golden_persons = set(golden_data[frame].keys())
                    annotator_persons = set(annotator_data[frame].keys())
                    common_persons = golden_persons.intersection(annotator_persons)

                    for person_id in common_persons:
                        label_a = annotator_data[frame][person_id].get(attr)
                        label_g = golden_data[frame][person_id].get(attr)

                        if label_a is not None and label_g is not None:
                            labels_annotator.append(label_a)
                            labels_golden.append(label_g)

                # 4. Calculate Kappa (if data exists)
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