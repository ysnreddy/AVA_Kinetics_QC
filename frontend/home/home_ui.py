import streamlit as st
st.set_page_config(
    page_title="AVA-Kinetics Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎬"
)

try:
    from task_creator_ui import render_task_creator
    task_creator_available = True
except ImportError as e:
    st.sidebar.error(f"Task Creator unavailable: {e}")
    task_creator_available = False

try:
    from qc_app import render_qc_dashboard
    qc_dashboard_available = True
except ImportError as e:
    st.sidebar.error(f"QC Dashboard unavailable: {e}")
    qc_dashboard_available = False

# ============================================================
# MAIN NAVIGATION
# ============================================================

# Build navigation options based on available modules
nav_options = []
if task_creator_available:
    nav_options.append("Task Creator")
if qc_dashboard_available:
    nav_options.append("QC Dashboard")

if not nav_options:
    st.error("❌ No modules available. Please ensure task_creator_ui.py and qc_app.py are in the same directory.")
    st.stop()

st.sidebar.title("🎬 AVA-Kinetics Pipeline")
st.sidebar.divider()

page = st.sidebar.radio(
    "🧭 Navigation",
    nav_options
)

st.sidebar.divider()
st.sidebar.markdown("### 📊 System Information")
st.sidebar.markdown("**Version:** 2.0")
st.sidebar.markdown("**Backend:** FastAPI + PostgreSQL")
st.sidebar.markdown("**Storage:** AWS S3")
st.sidebar.markdown("**Features:**")
st.sidebar.markdown("- ✅ Multi-annotator workflow")
st.sidebar.markdown("- ✅ Adjudication & audit")
st.sidebar.markdown("- ✅ Quality metrics")
st.sidebar.markdown("- ✅ Dataset generation")

if page == "Task Creator":
    if task_creator_available:
        render_task_creator()
    else:
        st.error("❌ Task Creator module not available")
        st.info("Please ensure `task_creator_ui.py` exists and contains a `render_task_creator()` function")

elif page == "QC Dashboard":
    if qc_dashboard_available:
        render_qc_dashboard() 
    else:
        st.error("❌ QC Dashboard module not available")
        st.info("Please ensure `qc_app.py` exists and contains a `render_qc_dashboard()` function")