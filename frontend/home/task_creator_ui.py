import streamlit as st
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()
def render_task_creator():
    st.title("🚀 CVAT Task Creator")

    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1/cvat")

    DEFAULT_CVAT_HOST = os.getenv("CVAT_HOST", "http://localhost:8080")
    DEFAULT_CVAT_USER = os.getenv("CVAT_USERNAME", "strawhat03")
    DEFAULT_CVAT_PASS = os.getenv("CVAT_PASSWORD", "test@123")
    DEFAULT_S3_BUCKET = os.getenv("AWS_STORAGE_BUCKET_NAME", "ava-new-kinetics")

    st.set_page_config("CVAT Task Creator (S3)", layout="wide")
    st.title("🚀 CVAT Task Creator (S3 + Local Annotations)")

    st.sidebar.header("⚙️ CVAT & S3 Config")
    cvat_host = st.sidebar.text_input("CVAT Host", DEFAULT_CVAT_HOST)
    cvat_user = st.sidebar.text_input("CVAT Username", DEFAULT_CVAT_USER)
    cvat_pass = st.sidebar.text_input("CVAT Password", DEFAULT_CVAT_PASS, type="password")
    s3_bucket = st.sidebar.text_input("S3 Bucket", DEFAULT_S3_BUCKET)

    st.header("1️⃣ Select Batch")

    if st.button("🔄 Load Batches"):
        resp = requests.post(
            f"{BACKEND_URL}/list-batches",
            json={"s3_bucket": s3_bucket},
        )
        st.session_state["batches"] = resp.json()["batches"]

    batch_name = st.selectbox(
        "Batch Name",
        st.session_state.get("batches", []),
    )

    st.header("2️⃣ Select Frame ZIPs")

    if batch_name:
        resp = requests.post(
            f"{BACKEND_URL}/list-frames-zips",
            json={
                "s3_bucket": s3_bucket,
                "batch_name": batch_name,
            },
        )
        zip_files = resp.json()["zip_files"]
        selected_zips = st.multiselect(
            "Frame ZIPs",
            zip_files,
            default=zip_files,
        )
    else:
        selected_zips = []

    st.header("3️⃣ Annotation Path")

    annotation_base_path = st.text_input(
        "Annotation Base Path (on server)",
        value="E:/ava-ui/proposal_generation_pipeline/proposal_generation_pipeline/outputs/",
        help="Must exist on the EC2 / server",
    )

    st.header("4️⃣ Create CVAT Project")

    project_name = st.text_input(
        "CVAT Project Name",
        f"S3_Project_{int(time.time())}",
    )

    annotators = st.text_input(
        "Annotators (comma-separated)",
    ).split(",")

    if st.button("🚀 Create Project & Tasks"):
        payload = {
            "host": cvat_host,
            "username": cvat_user,
            "password": cvat_pass,
            "s3_bucket": s3_bucket,
            "project_name": project_name,
            "batch_name": batch_name,
            "zip_files": selected_zips,
            "annotators": [a.strip() for a in annotators if a.strip()],
            "annotation_base_path": annotation_base_path,
        }

        with st.spinner("Creating tasks in CVAT..."):
            resp = requests.post(
                f"{BACKEND_URL}/create-project-tasks",
                json=payload,
            )

            if resp.status_code == 200:
                st.success("✅ Tasks created successfully")
                st.json(resp.json())
            else:
                st.error(resp.text)
