import psycopg2
import psycopg2.extras
import logging
import json
import random
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoutingService:
    def __init__(self, db_params):
        self.db_params = db_params
        # CHANGED: 60% sampling rate to satisfy the "Rule of Three" for <5% error
        self.audit_sample_rate = 0.60

    def _get_db_connection(self):
        return psycopg2.connect(**self.db_params)

    def _get_task_info(self, task_id):
        conn = self._get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT task_id, name, project_id, status, qc_status FROM tasks WHERE task_id = %s", (task_id,))
            task = cur.fetchone()
        conn.close()
        return task

    def _find_partner_task(self, task):
        task_name = task['name']
        parts = task_name.rsplit('_', 1)
        if len(parts) < 2: return None

        batch_name_prefix = parts[0]

        conn = self._get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT task_id, name, status, qc_status
                FROM tasks
                WHERE name LIKE %s
                  AND task_id != %s
                  AND project_id = %s
                """,
                (f"{batch_name_prefix}%", task['task_id'], task['project_id'])
            )
            partners = cur.fetchall()
        conn.close()
        if len(partners) == 1: return partners[0]
        return None

    def _fetch_annotations(self, task_id):
        conn = self._get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s",
                (task_id,)
            )
            rows = cur.fetchall()
        conn.close()
        data = defaultdict(dict)
        for row in rows:
            data[row['keyframe_name']][row['person_id']] = dict(row)
        return data

    def _calculate_iou(self, boxA, boxB):
        xA = max(boxA['xtl'], boxB['xtl'])
        yA = max(boxA['ytl'], boxB['ytl'])
        xB = min(boxA['xbr'], boxB['xbr'])
        yB = min(boxA['ybr'], boxB['ybr'])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA['xbr'] - boxA['xtl']) * (boxA['ybr'] - boxA['ytl'])
        boxBArea = (boxB['xbr'] - boxB['xtl']) * (boxB['ybr'] - boxB['ytl'])
        iou = interArea / float(boxAArea + boxBArea - interArea) if (boxAArea + boxBArea - interArea) > 0 else 0
        return iou

    def _calculate_jaccard(self, attrsA, attrsB):
        setA = set(f"{k}:{v}" for k, v in attrsA.items() if v and v != 'unknown')
        setB = set(f"{k}:{v}" for k, v in attrsB.items() if v and v != 'unknown')
        if not setA and not setB: return 1.0
        intersection = len(setA.intersection(setB))
        union = len(setA.union(setB))
        return intersection / union if union > 0 else 0.0

    def process_task(self, task_id):
        logger.info(f"Router: Checking routing for Task {task_id}...")
        current_task = self._get_task_info(task_id)
        if not current_task: return

        partner_task = self._find_partner_task(current_task)

        if not partner_task:
            new_status = 'pending_audit' if random.random() < self.audit_sample_rate else 'approved'
            self._update_status(task_id, new_status)
            return

        if partner_task['status'] != 'completed':
            logger.info(f"Router: Partner task {partner_task['task_id']} is not complete. Waiting.")
            return

        anns_A = self._fetch_annotations(task_id)
        anns_B = self._fetch_annotations(partner_task['task_id'])

        disagreement_found = False
        all_frames = set(anns_A.keys()) | set(anns_B.keys())

        for frame in all_frames:
            persons_A = anns_A.get(frame, {})
            persons_B = anns_B.get(frame, {})

            if len(persons_A) != len(persons_B):
                disagreement_found = True;
                break

            for pid in persons_A:
                if pid not in persons_B:
                    disagreement_found = True;
                    break

                if self._calculate_iou(persons_A[pid], persons_B[pid]) < 0.5:
                    disagreement_found = True;
                    break

                if self._calculate_jaccard(persons_A[pid]['attributes'], persons_B[pid]['attributes']) < 1.0:
                    disagreement_found = True;
                    break

            if disagreement_found: break

        conn = self._get_db_connection()
        cur = conn.cursor()

        if disagreement_found:
            logger.info("Router: Disagreement. Routing to 'pending_adjudication'.")
            status = 'pending_adjudication'
        else:
            # Agreement! Apply 60% Sampling Rule
            if random.random() < self.audit_sample_rate:
                logger.info("Router: Agreement. Selected for BLIND AUDIT (60% sample).")
                status = 'pending_audit'
                self._create_audit_entries(cur, task_id, partner_task['task_id'], anns_A)
            else:
                logger.info("Router: Agreement. Auto-Approving (skipped audit).")
                status = 'approved'

        cur.execute("UPDATE tasks SET qc_status = %s WHERE task_id IN (%s, %s)",
                    (status, task_id, partner_task['task_id']))
        conn.commit()
        conn.close()

    def _update_status(self, task_id, status):
        conn = self._get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE tasks SET qc_status = %s WHERE task_id = %s", (status, task_id))
        conn.commit()
        conn.close()

    def _create_audit_entries(self, cur, task_id_A, task_id_B, consensus_data):
        for frame, persons in consensus_data.items():
            for pid, data in persons.items():
                cur.execute(
                    """
                    INSERT INTO audits (task_id, keyframe_name, person_id, original_consensus_attributes)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (task_id_A, frame, pid, json.dumps(data['attributes']))
                )