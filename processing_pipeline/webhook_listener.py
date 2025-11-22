import ssl
from flask import Flask, request, jsonify
import subprocess
import json
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

# Construct the path to the service script relative to this file
# Structure: processing_pipeline/webhook_listener.py -> processing_pipeline/services/post_annotation_service.py
SCRIPT_PATH = os.path.join(BASE_DIR, "services", "post_annotation_service.py")

# Check if file exists at startup to warn you immediately
if not os.path.exists(SCRIPT_PATH):
    logger.warning(f"⚠️ CRITICAL: Script not found at {SCRIPT_PATH}")
    logger.warning("Please check your folder structure.")
else:
    logger.info(f"✅ Service script detected at: {SCRIPT_PATH}")

@app.route('/webhook', methods=['POST'])
def cvat_webhook():
    """ This endpoint listens for 'update:task' or 'update:job' events and triggers post-annotation service on completion. """
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON."}), 400

    payload = request.get_json()
    # logger.info(f"Received webhook payload: {json.dumps(payload, indent=2)}") # Uncomment for debugging

    event = payload.get("event")
    task_id = None
    assignee = "N/A"

    # --- Logic to find the completed Task/Job ID ---
    
    # 1. Check for a completed TASK update
    if event == "update:task":
        task_info = payload.get("task", {})
        if task_info.get("status") == "completed":
            task_id = task_info.get("id")
            # assignee is often null in task updates, fallback to N/A
            assignee = (task_info.get("assignee") or {}).get("username", "N/A") 

    # 2. Check for a completed JOB update
    elif event == "update:job":
        job_info = payload.get("job", {})
        if job_info.get("state") == "completed": 
            task_id = job_info.get("task_id")
            # Robust assignee extraction
            assignee = (job_info.get("assignee") or {}).get("username", (payload.get("sender") or {}).get("username", "N/A"))
            
    # --- End Logic ---

    if task_id:
        logger.info(f"✅ Job/Task {task_id} completed by {assignee}. Triggering post-annotation service...")

        try:
            # Trigger the post_annotation_service.py script as a background process
            # We use sys.executable to ensure we use the same python environment (Docker/Virtualenv) running this script
            subprocess.Popen(
                [
                    sys.executable, 
                    SCRIPT_PATH, 
                    "--task-id", str(task_id),
                    "--assignee", assignee 
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({"status": "success", "message": "Post-annotation service triggered."}), 200
        except Exception as e:
            logger.error(f"Failed to trigger post-annotation service: {e}")
            return jsonify({"status": "error", "message": "Failed to trigger service."}), 500

    return jsonify({"status": "ignored", "message": f"Event was not a completion event (received: {event})."}), 200

if __name__ == '__main__':
    # Host 0.0.0.0 allows external access (vital for Docker)
    app.run(host='0.0.0.0', port=5001,debug=True)
    # For production, consider using a proper SSL certificate instead of 'adhoc'
    #import ssl
    #context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    #context.load_cert_chain('cert.pem', 'key.pem')
    # app.run(host='0.0.0.0', port=5001, ssl_context=context, debug=False)