from flask import Flask, request, jsonify
import subprocess
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- PATH CONFIGURATION ---
# Get the directory where THIS file (webhook_listener.py) is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the Root of your project (Go up one level from 'processing_pipeline')
# This fixes the [Errno 13] Permission denied errors
PROJECT_ROOT = os.path.dirname(BASE_DIR) 

# Construct the path to the service script relative to this file
SCRIPT_PATH = os.path.join(BASE_DIR, "services", "post_annotation_service.py")

# Check if file exists at startup to warn you immediately
if not os.path.exists(SCRIPT_PATH):
    logger.warning(f"⚠️ CRITICAL: Script not found at {SCRIPT_PATH}")
else:
    logger.info(f"✅ Service script detected at: {SCRIPT_PATH}")
    logger.info(f"📂 Working Directory set to: {PROJECT_ROOT}")

@app.route('/webhook', methods=['POST'])
def cvat_webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON."}), 400

    payload = request.get_json()
    event = payload.get("event")
    task_id = None
    assignee = "N/A"

    # --- Logic to find the completed Task/Job ID ---
    if event == "update:task":
        task_info = payload.get("task", {})
        if task_info.get("status") == "completed":
            task_id = task_info.get("id")
            assignee = (task_info.get("assignee") or {}).get("username", "N/A") 

    elif event == "update:job":
        job_info = payload.get("job", {})
        if job_info.get("state") == "completed": 
            task_id = job_info.get("task_id")
            assignee = (job_info.get("assignee") or {}).get("username", (payload.get("sender") or {}).get("username", "N/A"))

    if task_id:
        logger.info(f"✅ Job/Task {task_id} completed by {assignee}. Triggering post-annotation service...")

        try:
            # FIX 1: Use subprocess.PIPE to capture errors (instead of DEVNULL)
            # FIX 2: Use cwd=PROJECT_ROOT so imports and file paths work correctly
            process = subprocess.Popen(
                [
                    sys.executable, 
                    SCRIPT_PATH, 
                    "--task-id", str(task_id),
                    "--assignee", str(assignee) 
                ],
                cwd=PROJECT_ROOT,  # <--- CRITICAL FIX
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for execution to see if it crashes
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                logger.info(f"Service Output: {stdout}")
                return jsonify({"status": "success", "message": "Service triggered successfully"}), 200
            else:
                logger.error(f"Service Failed with Error: {stderr}")
                return jsonify({"status": "error", "message": f"Script failed: {stderr}"}), 500

        except Exception as e:
            logger.error(f"Failed to trigger post-annotation service: {e}")
            return jsonify({"status": "error", "message": "Failed to trigger service."}), 500

    return jsonify({"status": "ignored", "message": f"Event was not a completion event (received: {event})."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)