import requests
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CVATClient:
    def __init__(self, host: str, username: str, password: str):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token = None
        self.authenticated = self.login()

    def login(self) -> bool:
        try:
            url = f"{self.host}/api/auth/login"
            resp = self.session.post(url, json={"username": self.username, "password": self.password}, timeout=30)
            resp.raise_for_status()
            self.token = resp.json()["key"]
            self.session.headers.update({"Authorization": f"Token {self.token}"})
            logger.info(f"✓ Login successful for user: {self.username}")
            return True
        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False

    def _make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        if not self.authenticated:
            raise RuntimeError("Client is not authenticated.")
        kwargs.setdefault("timeout", 300)
        try:
            return self.session.request(method.upper(), url, **kwargs)
        except Exception as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise

    def create_project(self, name: str, labels: List[Dict[str, Any]], org_slug: str = None) -> Optional[int]:
        try:
            payload = {"name": name, "labels": labels}
            if org_slug: payload['org'] = org_slug
            
            resp = self._make_authenticated_request('POST', f"{self.host}/api/projects", json=payload)
            if resp.status_code == 201:
                project_id = resp.json()["id"]
                logger.info(f"✓ Project '{name}' created with ID: {project_id}")
                return project_id
            else:
                logger.error(f"Failed to create project: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Exception creating project: {e}")
            return None

    def create_task(self, name: str, project_id: int) -> Optional[int]:
        try:
            payload = {"name": name, "project_id": project_id}
            resp = self._make_authenticated_request('POST', f"{self.host}/api/tasks", json=payload)
            if resp.status_code == 201:
                task_id = resp.json()["id"]
                logger.info(f"✓ Task '{name}' created with ID: {task_id}")
                return task_id
            logger.error(f"Failed to create task: {resp.status_code} - {resp.text}")
            return None
        except Exception as e:
            logger.error(f"Exception creating task: {e}")
            return None

    def upload_data_to_task(self, task_id: int, zip_file_path: str) -> bool:
        try:
            with open(zip_file_path, 'rb') as fh:
                files = {'client_files[0]': (os.path.basename(zip_file_path), fh, 'application/zip')}
                data = {'image_quality': '95'}
                resp = self._make_authenticated_request('POST', f"{self.host}/api/tasks/{task_id}/data", files=files, data=data)
            if resp.status_code != 202:
                logger.error(f"Data upload failed to start: {resp.status_code} - {resp.text}")
                return False
            
            rq_id = resp.json()['rq_id']
            while True:
                status_resp = self._make_authenticated_request("GET", f"{self.host}/api/requests/{rq_id}")
                status = status_resp.json().get("status")
                if status == "finished":
                    logger.info(f"✓ Data upload for task {task_id} complete.")
                    return True
                if status == "failed":
                    logger.error(f"Data upload processing failed: {status_resp.json()}")
                    return False
                time.sleep(3)
        except Exception as e:
            logger.error(f"Exception uploading data: {e}")
            return False

    def import_annotations(self, task_id: int, xml_file: str) -> bool:
        try:
            url = f"{self.host}/api/tasks/{task_id}/annotations?action=upload&format=CVAT%201.1"
            with open(xml_file, "rb") as fh:
                files = {"annotation_file": (os.path.basename(xml_file), fh, "application/xml")}
                resp = self._make_authenticated_request("POST", url, files=files)
            if resp.status_code not in (201, 202):
                logger.error(f"Annotation import failed: {resp.status_code} - {resp.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Exception importing annotations: {e}")
            return False

    def assign_user_to_task(self, task_id: int, username: str) -> bool:
        try:
            resp_user = self._make_authenticated_request('GET', f"{self.host}/api/users", params={"search": username})
            if not resp_user.json().get('results'):
                logger.error(f"Could not find user '{username}' in CVAT.")
                return False
            user_id = resp_user.json()['results'][0]['id']
            
            resp_jobs = self._make_authenticated_request('GET', f"{self.host}/api/jobs", params={"task_id": task_id})
            jobs = resp_jobs.json().get('results', [])
            
            for job in jobs:
                self._make_authenticated_request('PATCH', f"{self.host}/api/jobs/{job['id']}", json={'assignee': user_id})
            logger.info(f"✓ Assigned task {task_id} to '{username}'")
            return True
        except Exception as e:
            logger.error(f"Exception assigning user to task {task_id}: {e}")
            return False

    def create_tasks_from_packages(
        self,
        project_id: int,
        package_dir: str,
        batch_name: str
    ) -> List[Dict]:
        package_path = Path(package_dir)
        results = []
        
        zip_files = list(package_path.glob(f"{batch_name}_*_keyframes.zip"))
        if not zip_files:
            logger.error(f"No keyframe packages found in '{package_path}' for batch '{batch_name}'")
            return results

        logger.info(f"Found {len(zip_files)} packages to process for batch '{batch_name}'")

        for zip_path in zip_files:
            base_name = zip_path.name.replace('_keyframes.zip', '')
            annotator = base_name.replace(f"{batch_name}_", "")
            task_name = base_name

            xml_path = package_path / f"{task_name}_annotations.xml"
            if not xml_path.exists():
                logger.error(f"Matching XML file not found for {zip_path.name}, skipping.")
                continue

            logger.info(f"--- Processing package for annotator: {annotator} ---")

            task_id = self.create_task(task_name, project_id)
            if not task_id: continue
            if not self.upload_data_to_task(task_id, str(zip_path)): continue
            if not self.import_annotations(task_id, str(xml_path)): continue
            if not self.assign_user_to_task(task_id, annotator): continue

            results.append({'task_id': task_id, 'task_name': task_name, 'annotator': annotator})

        return results

    def create_project_and_add_tasks(
        self,
        project_name: str,
        package_dir: str,
        batch_name: str
    ) -> Optional[Dict]:
        logger.info(f"Attempting to create new project: '{project_name}'")
        project_id = self.create_project(project_name, get_default_labels())
        if not project_id:
            logger.error("Failed to create project. Aborting.")
            return None
        
        logger.info(f"✓ Project created successfully with ID: {project_id}. Now adding tasks...")
        results = self.create_tasks_from_packages(
            project_id=project_id,
            package_dir=package_dir,
            batch_name=batch_name
        )
        return {"project_id": project_id, "tasks_created": results}

# --- THIS FUNCTION WAS MISSING - IT IS NOW INCLUDED ---
def get_default_labels() -> List[Dict[str, Any]]:
    """Defines the full label schema for the CVAT project."""
    return [
        {
            "name": "person",
            "color": "#ff0000",
            "attributes": [
                {"name": "ppe_helmet", "mutable": True, "input_type": "select", "default_value": "helmet_worn", "values": ["helmet_worn", "no_helmet", "helmet_incorrect"]},
                {"name": "ppe_vest", "mutable": True, "input_type": "select", "default_value": "vest_worn", "values": ["vest_worn", "no_vest"]},
                {"name": "ppe_gloves", "mutable": True, "input_type": "select", "default_value": "gloves_worn", "values": ["gloves_worn", "no_gloves"]},
                {"name": "ppe_boots", "mutable": True, "input_type": "select", "default_value": "safety_boots_worn", "values": ["safety_boots_worn", "no_safety_boots"]},
                {"name": "work_activity", "mutable": True, "input_type": "select", "default_value": "idle", "values": ["idle", "welding", "cutting", "climbing", "lifting_materials", "machine_operation", "supervising", "walking"]},
                {"name": "posture_safety", "mutable": True, "input_type": "select", "default_value": "upright_normal", "values": ["upright_normal", "bending", "overreaching", "unsafe_posture"]},
                {"name": "hazard_proximity", "mutable": True, "input_type": "select", "default_value": "safe_zone", "values": ["safe_zone", "near_hot_surface", "near_heavy_load", "near_moving_machine", "near_open_edge"]},
                {"name": "team_interaction", "mutable": True, "input_type": "select", "default_value": "working_alone", "values": ["working_alone", "pair_work", "small_team", "large_group", "supervisor_present"]},
            ]
        }
    ]