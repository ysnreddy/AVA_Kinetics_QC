from flask import Flask, request, jsonify
import subprocess
import json
import logging
import os
import sys
import ssl

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- PATH CONFIGURATION ---
# Get the directory where THIS file (webhook_listener.py) is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the service script relative to this file
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
    logger.info(f"Received webhook from {request.remote_addr}")

    event = payload.get("event")
    task_id = None
    assignee = "N/A"

    # --- Logic to find the completed Task/Job ID ---

    # 1. Check for a completed TASK update
    if event == "update:task":
        task_info = payload.get("task", {})
        if task_info.get("status") == "completed":
            task_id = task_info.get("id")
            assignee = (task_info.get("assignee") or {}).get("username", "N/A")

    # 2. Check for a completed JOB update
    elif event == "update:job":
        job_info = payload.get("job", {})
        if job_info.get("state") == "completed":
            task_id = job_info.get("task_id")
            assignee = (job_info.get("assignee") or {}).get("username", (payload.get("sender") or {}).get("username", "N/A"))

    # --- End Logic ---

    if task_id:
        logger.info(f"✅ Job/Task {task_id} completed by {assignee}. Triggering post-annotation service...")

        try:
            # Trigger the post_annotation_service.py script as a background process
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to test connectivity"""
    return jsonify({"status": "healthy", "service": "webhook_listener"}), 200

if __name__ == '__main__':
    # For HTTPS support with self-signed certificate
    # First, generate certificates if they don't exist
    cert_dir = os.path.join(BASE_DIR, 'certs')
    cert_file = os.path.join(cert_dir, 'cert.pem')
    key_file = os.path.join(cert_dir, 'key.pem')

    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
        logger.info(f"Created certificate directory: {cert_dir}")

    # Check if certificates exist
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        logger.error("⚠️ SSL certificates not found. Generate them with:")
        logger.error(f"openssl req -x509 -newkey rsa:4096 -nodes -out {cert_file} -keyout {key_file} -days 365")
        logger.info("Falling back to HTTP...")
        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        logger.info("✅ Starting webhook listener with HTTPS support on port 5001")
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(cert_file, key_file)

        # Run with SSL
        app.run(host='0.0.0.0', port=5001, debug=True, ssl_context=context)