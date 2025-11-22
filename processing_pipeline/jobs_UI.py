import streamlit as st
from pathlib import Path
import time

# Adjust the import path if your file structure is different
try:
    from services.cvat_integration import CVATClient
except ImportError:
    st.error("Could not import custom services. Make sure this app is run from your project's root directory.")
    st.stop()


# --- Page Configuration ---
st.set_page_config(page_title="CVAT Project & Task Creator", layout="wide")
st.title("🚀 CVAT Automated Project & Task Creator")
st.markdown("This app creates a new project with the correct labels, then uploads all packages for a batch.")


# --- Sidebar for Configuration ---
st.sidebar.header("⚙️ Configuration")
cvat_host = st.sidebar.text_input("CVAT Host URL", "http://localhost:8080")
cvat_user = st.sidebar.text_input("CVAT Username", "Strawhat03")
cvat_pass = st.sidebar.text_input("CVAT Password", "Test@123", type="password")
package_dir_str = st.sidebar.text_input("Path to Output Packages Directory", "F:/ava_kinetics - Copy/AVA_kinetics_multiAnnotator_pipeline/proposal_generation_pipeline/proposal_generation_pipeline/outputs")


# --- Main Page for Task Creation ---
st.header("Step 1: Define the Project and Batch")
project_name = st.text_input("New Project Name", f"Factory-Project-{int(time.time())}")
batch_name = st.text_input("Batch Name to Upload (e.g., 'factory_01')", "factory_01")

st.header("Step 2: Execute")

if st.button("🚀 Create Project and Upload All Tasks", type="primary"):
    package_dir = Path(package_dir_str)

    # --- Input Validation ---
    if not all([cvat_host, cvat_user, cvat_pass, project_name, batch_name]):
        st.error("Please fill in all configuration settings and names.")
        st.stop()
    if not package_dir.is_dir():
        st.error(f"Package directory not found at: '{package_dir.resolve()}'")
        st.stop()

    with st.spinner("Connecting to CVAT, creating project, and uploading packages..."):
        try:
            client = CVATClient(host=cvat_host, username=cvat_user, password=cvat_pass)

            if not client.authenticated:
                st.error("CVAT Authentication Failed! Check credentials.")
                st.stop()
            
            st.info("Authentication successful. Starting process...")

            # --- Call the orchestration function that creates the project first ---
            result = client.create_project_and_add_tasks(
                project_name=project_name,
                package_dir=str(package_dir),
                batch_name=batch_name
            )

            # --- Display Results ---
            st.subheader("✅ Results")
            if result and result.get("tasks_created"):
                st.success(f"Successfully created Project ID {result['project_id']} and added {len(result['tasks_created'])} tasks!")
                st.json(result)
                st.balloons()
            else:
                st.error("Process failed. Check the terminal logs for specific errors.")

        except Exception as e:
            st.error("An unexpected error occurred:")
            st.exception(e)