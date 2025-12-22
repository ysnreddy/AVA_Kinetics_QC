import requests
import logging
import time
import boto3
import os
from typing import List, Dict, Any, Optional
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processing_pipeline.services.label_loader import load_cvat_labels
from .label_loader import load_cvat_labels

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CVATClient:
    """
    FINAL STABLE CVAT CLIENT

    ✔ Frames: S3 (presigned URL)
    ✔ Annotations: LOCAL FILESYSTEM (dynamic path)
    ✔ No cloud_storage_id headaches
    ✔ No S3 annotation download cost
    ✔ Works with existing UI + router
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        s3_bucket: Optional[str] = None,
        annotation_base_path: Optional[str] = None,
    ):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.annotation_base_path = annotation_base_path

        self.session = requests.Session()
        self.token = None
        self.authenticated = self._login()

        self.s3_bucket = s3_bucket
        self.s3 = boto3.client("s3") if s3_bucket else None

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------
    def _login(self) -> bool:
        resp = self.session.post(
            f"{self.host}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["key"]
        self.session.headers.update(
            {"Authorization": f"Token {self.token}"}
        )
        logger.info(f"✓ CVAT login successful for '{self.username}'")
        return True

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        if not self.authenticated:
            raise RuntimeError("CVAT client not authenticated")

        resp = self.session.request(
            method.upper(),
            f"{self.host}{endpoint}",
            timeout=300,
            **kwargs,
        )
        resp.raise_for_status()
        return resp
        # ------------------------------------------------------------------
    # BACKWARD COMPATIBILITY (IMPORTANT)
    # ------------------------------------------------------------------
    def _make_authenticated_request(self, method: str, url: str, **kwargs):
        """
        Compatibility layer for older services (PostAnnotationService).
        Internally delegates to the new _request() method.
        """
        # Convert absolute URL to endpoint
        if url.startswith(self.host):
            endpoint = url.replace(self.host, "")
        else:
            endpoint = url

        return self._request(method, endpoint, **kwargs)


    # ------------------------------------------------------------------
    # S3
    # ------------------------------------------------------------------
    def generate_presigned_url(self, key: str, expiry: int = 3600) -> str:
        if not self.s3 or not self.s3_bucket:
            raise RuntimeError("S3 not configured")

        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.s3_bucket, "Key": key},
            ExpiresIn=expiry,
        )

    # ------------------------------------------------------------------
    # PROJECT / TASK
    # ------------------------------------------------------------------
    def create_project(self, name: str) -> int:
        resp = self._request(
            "POST",
            "/api/projects",
            json={
                "name": name,
                "labels": load_cvat_labels(),
            },
        )
        pid = resp.json()["id"]
        logger.info(f"✓ Project '{name}' created (ID={pid})")
        return pid

    def create_task(self, name: str, project_id: int) -> int:
        resp = self._request(
            "POST",
            "/api/tasks",
            json={
                "name": name,
                "project_id": project_id,
            },
        )
        tid = resp.json()["id"]
        logger.info(f"✓ Task '{name}' created (ID={tid})")
        return tid

    # ------------------------------------------------------------------
    # FRAMES (S3 → CVAT)
    # ------------------------------------------------------------------
    def upload_frames_from_s3(self, task_id: int, zip_key: str):
        presigned_zip = self.generate_presigned_url(zip_key)

        resp = self._request(
            "POST",
            f"/api/tasks/{task_id}/data",
            json={
                "remote_files": [presigned_zip],
                "image_quality": 95,
            },
        )

        rq_id = resp.json()["rq_id"]

        while True:
            status = self._request(
                "GET", f"/api/requests/{rq_id}"
            ).json()

            if status["status"] == "finished":
                logger.info(f"✓ Media ingestion complete for task {task_id}")
                return

            if status["status"] == "failed":
                raise RuntimeError(status)

            time.sleep(3)

    # ------------------------------------------------------------------
    # ANNOTATIONS (LOCAL FILESYSTEM)
    # ------------------------------------------------------------------
    def upload_annotations_local(
        self,
        task_id: int,
        batch_name: str,
        task_name: str,
    ):
        if not self.annotation_base_path:
            raise RuntimeError("annotation_base_path not provided")

        xml_path = os.path.join(
            self.annotation_base_path,
            batch_name,
            f"{task_name}_annotations.xml",
        )

        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"Annotation not found: {xml_path}")

        with open(xml_path, "rb") as f:
            files = {
                "annotation_file": (
                    os.path.basename(xml_path),
                    f,
                    "application/xml",
                )
            }

            self._request(
                "POST",
                f"/api/tasks/{task_id}/annotations?action=upload&format=CVAT%201.1",
                files=files,
            )

        logger.info(f"✓ Annotations uploaded for task {task_id}")

    # ------------------------------------------------------------------
    # ASSIGN ANNOTATOR
    # ------------------------------------------------------------------
    def assign_annotator(self, task_id: int, username: str):
        users = self._request(
            "GET", "/api/users", params={"search": username}
        ).json().get("results", [])

        if not users:
            logger.warning(f"Annotator '{username}' not found in CVAT")
            return

        user_id = users[0]["id"]

        jobs = self._request(
            "GET", "/api/jobs", params={"task_id": task_id}
        ).json().get("results", [])

        for job in jobs:
            self._request(
                "PATCH",
                f"/api/jobs/{job['id']}",
                json={"assignee": user_id},
            )

        logger.info(f"✓ Assigned '{username}' to task {task_id}")

    # ------------------------------------------------------------------
    # FULL PIPELINE
    # ------------------------------------------------------------------
    def create_project_and_add_tasks_from_s3(
        self,
        project_name: str,
        batch_name: str,
        zip_files: List[str],
        annotators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        project_id = self.create_project(project_name)
        tasks = []

        for zip_name in zip_files:
            task_name = zip_name.replace("_keyframes.zip", "")
            annotator = task_name.replace(f"{batch_name}_", "")

            logger.info(f"Processing task '{task_name}'")

            task_id = self.create_task(task_name, project_id)

            zip_key = f"{batch_name}/frames_zip/{zip_name}"

            self.upload_frames_from_s3(task_id, zip_key)
            self.upload_annotations_local(task_id, batch_name, task_name)

            if annotators and annotator in annotators:
                self.assign_annotator(task_id, annotator)

            tasks.append(
                {
                    "task_id": task_id,
                    "task_name": task_name,
                    "annotator": annotator,
                }
            )

        return {
            "project_id": project_id,
            "tasks_created": tasks,
        }
