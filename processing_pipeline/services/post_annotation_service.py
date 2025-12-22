import argparse
import logging
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import time
import io
import zipfile
import os
import psycopg2
import psycopg2.extras
import sys

# Ensure we can find the sibling modules (Adjust relative path as needed for your folder structure)
# Assuming file is in processing_pipeline/services/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    from processing_pipeline.services.cvat_integration import CVATClient
    # Assuming these are in the root or processing_pipeline folder in your structure
    # If RuleEngine/RoutingService are in 'services', change import to .rule_engine / .routing_service
    # Based on your logs, the path append above seems to handle the root imports.
    from processing_pipeline.services.rule_engine import RuleEngine
    from processing_pipeline.services.routing_service import RoutingService
except ImportError:
    # Fallback for running directly from root
    try:
        from services.cvat_integration import CVATClient
        from rule_engine import RuleEngine
        from routing_service import RoutingService
    except ImportError:
        logging.error("Could not import required modules. Check your python path.")
        sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PostAnnotationService:
    def __init__(self, db_params: Dict[str, str], cvat_client: CVATClient):
        self.db_params = db_params
        self.cvat_client = cvat_client
        self.conn = None
        # Initialize the Rule Engine
        self.rule_engine = RuleEngine()
        self.router = RoutingService(db_params)

    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**self.db_params)
            logger.info("✓ Successfully connected to PostgreSQL.")
            return True
        except psycopg2.OperationalError as e:
            logger.error(f"✗ Could not connect to the database: {e}")
            return False

    def close_db(self):
        if self.conn: self.conn.close()

    def _wait_for_request_completion(self, rq_id: str, timeout: int = 300) -> Optional[Dict]:
        """Polls a request ID until it is finished or failed."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_resp = self.cvat_client._make_authenticated_request("GET",
                                                                       f"{self.cvat_client.host}/api/requests/{rq_id}")
            if status_resp.status_code != 200: return None
            status_data = status_resp.json()
            status = status_data.get("status")
            if status in ("finished", "failed"):
                return status_data
            time.sleep(3)
        logger.error(f"✗ Job {rq_id} timed out.")
        return None

    def export_annotations_from_task(self, task_id: int) -> Optional[str]:
        """Exports annotations for a task using the robust POST asynchronous method."""
        try:
            # Use POST as required by your CVAT version
            url = f"{self.cvat_client.host}/api/tasks/{task_id}/dataset/export"
            params = {"format": "CVAT for images 1.1", "save_images": False}
            resp = self.cvat_client._make_authenticated_request("POST", url, params=params)

            if resp.status_code != 202:
                logger.error(f"Failed to start export for task {task_id}: {resp.status_code} - {resp.text}")
                return None

            rq_id = resp.json()['rq_id']
            logger.info(f"Started annotation export job {rq_id} for task {task_id}")
            status_data = self._wait_for_request_completion(rq_id)

            if not status_data or status_data.get("status") != "finished":
                logger.error(f"Annotation export failed or timed out. Status: {status_data}")
                return None

            result_url = status_data.get("result_url")
            if not result_url: return None

            download_resp = self.cvat_client._make_authenticated_request("GET", result_url, stream=True)
            download_resp.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(download_resp.content)) as z:
                for filename in z.namelist():
                    if filename.lower().endswith('.xml'):
                        xml_data = z.read(filename).decode('utf-8')
                        logger.info(f"✓ Successfully extracted '{filename}' for task {task_id}.")
                        return xml_data

            logger.error("Could not find annotations.xml in the exported zip file.")
            return None

        except Exception as e:
            logger.error(f"Failed to export annotations for task {task_id}: {e}")
            return None

    def process_and_store_task(self, task_id: int, assignee_override: str = None):
        """
        Handles the full workflow: Fetch -> Validate -> Store -> Flag.
        Uses assignee_override if provided (from webhook), otherwise fetches from API.
        """
        if not self.connect_db(): return

        try:
            logger.info(f"Processing completed task {task_id}...")

            # 1. Fetch Task Meta
            task_resp = self.cvat_client._make_authenticated_request("GET",
                                                                     f"{self.cvat_client.host}/api/tasks/{task_id}")
            if task_resp.status_code != 200:
                logger.error(f"Could not fetch details for task {task_id}")
                return
            task_details = task_resp.json()
            project_id = task_details.get("project_id")
            task_name = task_details.get("name")

            # Determine Assignee: Use override if present, else fetch from task details
            if assignee_override and assignee_override != "N/A" and assignee_override != "None":
                assignee = assignee_override
            else:
                assignee = (task_details.get("assignee") or {}).get("username", "N/A")
            
            logger.info(f"Assignee determined as: {assignee}")

            # 2. Ensure Project Exists (Foreign Key Fix)
            if project_id:
                with self.conn.cursor() as cur:
                    proj_resp = self.cvat_client._make_authenticated_request("GET",
                                                                             f"{self.cvat_client.host}/api/projects/{project_id}")
                    proj_name = proj_resp.json().get("name",
                                                     f"Project_{project_id}") if proj_resp.status_code == 200 else f"Project_{project_id}"

                    cur.execute(
                        "INSERT INTO projects (project_id, name) VALUES (%s, %s) ON CONFLICT (project_id) DO NOTHING;",
                        (project_id, proj_name)
                    )

            # 3. Export & Parse
            xml_data = self.export_annotations_from_task(task_id)
            if not xml_data: return

            root = ET.fromstring(xml_data)
            annotations_to_insert = []
            flags_to_insert = []
            has_blocking_errors = False

            # Loop through images and boxes
            for image_tag in root.findall("image"):
                keyframe_name = image_tag.get("name")

                for person_id_counter, box_tag in enumerate(image_tag.findall("box")):
                    attributes = {attr.get("name"): attr.text for attr in box_tag.findall("attribute")}

                    xtl, ytl = float(box_tag.get("xtl")), float(box_tag.get("ytl"))
                    xbr, ybr = float(box_tag.get("xbr")), float(box_tag.get("ybr"))

                    # --- VALIDATION STEP ---
                    box_area = (xbr - xtl) * (ybr - ytl)
                    validation_flags = self.rule_engine.validate_annotation(attributes, box_area)

                    # If flags exist, record them
                    for flag in validation_flags:
                        flags_to_insert.append((
                            task_id,
                            keyframe_name,
                            flag['issue'],
                            flag['severity'],
                            json.dumps(flag.get('details', {}))
                        ))
                        if flag['severity'] == 'block':
                            has_blocking_errors = True

                    # Prepare annotation for insertion
                    annotations_to_insert.append((
                        task_id,
                        keyframe_name,
                        person_id_counter + 1,  # Simple person ID
                        xtl, ytl, xbr, ybr,
                        json.dumps(attributes)
                    ))

            # 4. DB Transaction
            with self.conn.cursor() as cur:
                # A. Update Task Record
                # Set status based on validation
                initial_qc_status = 'rejected' if has_blocking_errors else 'pending'

                cur.execute(
                    """
                    INSERT INTO tasks (task_id, project_id, name, status, assignee, retrieved_at, qc_status)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s) ON CONFLICT (task_id) DO
                    UPDATE SET
                        status = EXCLUDED.status,
                        assignee = EXCLUDED.assignee,
                        retrieved_at = EXCLUDED.retrieved_at,
                        qc_status = EXCLUDED.qc_status;
                    """,
                    (task_id, project_id, task_name, 'completed', assignee, initial_qc_status)
                )

                # B. Clear Old Data
                cur.execute("DELETE FROM annotations WHERE task_id = %s;", (task_id,))
                cur.execute("DELETE FROM qc_flags WHERE task_id = %s;", (task_id,))

                # C. Insert New Annotations
                if annotations_to_insert:
                    psycopg2.extras.execute_values(
                        cur,
                        "INSERT INTO annotations (task_id, keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes) VALUES %s",
                        annotations_to_insert
                    )

                # D. Insert QC Flags
                if flags_to_insert:
                    psycopg2.extras.execute_values(
                        cur,
                        "INSERT INTO qc_flags (task_id, keyframe_name, issue_type, severity, details) VALUES %s",
                        flags_to_insert
                    )

            self.conn.commit()
            logger.info(
                f"✓ Task {task_id} processed. Annotations: {len(annotations_to_insert)}, Flags: {len(flags_to_insert)}, Status: {initial_qc_status}")
            if initial_qc_status != 'rejected':
                self.router.process_task(task_id)

        except Exception as e:
            logger.error(f"Database transaction failed for task {task_id}: {e}")
            if self.conn: self.conn.rollback()
        finally:
            self.close_db()


def parse_args():
    parser = argparse.ArgumentParser(description="Sync a completed CVAT task to a PostgreSQL database.")
    parser.add_argument("--task-id", required=True, type=int, help="CVAT task ID to sync.")
    # ADDED: Optional assignee argument to prevent Webhook crashes
    parser.add_argument("--assignee", type=str, default=None, help="Username of the assignee (optional)")
    return parser.parse_args()


if __name__ == "__main__":
    # Update these credentials for your environment
    DB_PARAMS = {"dbname": "cvat_annotations_db", "user": "admin", "password": "admin", "host": "localhost",
                 "port": "55432"}
    CVAT_HOST = "http://localhost:8080"
    CVAT_USERNAME = "Strawhat03"
    CVAT_PASSWORD = "test@123"

    args = parse_args()
    try:
        cvat_client = CVATClient(host=CVAT_HOST, username=CVAT_USERNAME, password=CVAT_PASSWORD)
        if cvat_client.authenticated:
            service = PostAnnotationService(db_params=DB_PARAMS, cvat_client=cvat_client)
            # Pass the assignee from arguments to the service
            service.process_and_store_task(task_id=args.task_id, assignee_override=args.assignee)
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")