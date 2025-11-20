from flask import Flask, request, jsonify
import subprocess
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Define the root of your project where Python path resolution begins (F:\ava_kinetics)
PROJECT_ROOT = r"F:\ava_kinetics" 

# Define the full, raw path to the post_annotation_service.py script
SCRIPT_PATH = r"services/post_annotation_service.py"

@app.route('/webhook', methods=['POST'])
def cvat_webhook():
    """ This endpoint listens for 'update:task' or 'update:job' events and triggers post-annotation service on completion. """
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON."}), 400

    payload = request.get_json()
    logger.info(f"Received webhook payload: {json.dumps(payload, indent=2)}")

    event = payload.get("event")
    task_id = None
    assignee = "N/A"

    # --- Logic to find the completed Task/Job ID ---
    
    # 1. Check for a completed TASK update
    if event == "update:task":
        task_info = payload.get("task", {})
        if task_info.get("status") == "completed":
            task_id = task_info.get("id")
            # This task_info.get("assignee") is often null, but we'll use the job one below if available
            assignee = (task_info.get("assignee") or {}).get("username", "N/A") 

    # 2. Check for a completed JOB update
    elif event == "update:job":
        job_info = payload.get("job", {})
        if job_info.get("state") == "completed": 
            task_id = job_info.get("task_id")
            # FIX: Get the reliable assignee from the job payload
            assignee = (job_info.get("assignee") or {}).get("username", (payload.get("sender") or {}).get("username", "N/A"))
            
    # --- End Logic ---

    if task_id:
        logger.info(f"✅ Job/Task {task_id} completed by {assignee}. Triggering post-annotation service...")

        try:
            # Trigger the post_annotation_service.py script as a background process
            subprocess.Popen(
                [
                    "python", 
                    SCRIPT_PATH, 
                    "--task-id", str(task_id),
                    # FIX: Pass the assignee name as a command-line argument
                    "--assignee", assignee 
                ],
                # Ensure the correct working directory is used for relative imports
                cwd=PROJECT_ROOT, 
                
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({"status": "success", "message": "Post-annotation service triggered."}), 200
        except Exception as e:
            logger.error(f"Failed to trigger post-annotation service: {e}")
            return jsonify({"status": "error", "message": "Failed to trigger service."}), 500

    return jsonify({"status": "ignored", "message": f"Event was not a completion event (received: {event})."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)