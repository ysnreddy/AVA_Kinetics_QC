import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from pathlib import Path
import os
import json
import cv2
import numpy as np
from collections import defaultdict

# --- Imports (with Error Handling) ---
try:
    from services.dataset_generator import DatasetGenerator, ATTRIBUTE_DEFINITIONS
    from services.qc_service import QCService
except ImportError:
    st.error(
        "Could not import services. Make sure you are running this from the project root and 'dataset_generator.py', 'qc_service.py' are in 'tools/'.")
    st.stop()

# --- Configuration ---
st.set_page_config(page_title="AVA-Kinetics QC Dashboard", layout="wide")
st.title("🔬 AVA-Kinetics QC Dashboard")

st.sidebar.header("⚙️ Database Configuration")
db_params = {
    "dbname": st.sidebar.text_input("DB Name", "cvat_annotations_db"),
    "user": st.sidebar.text_input("DB User", "admin"),
    "password": st.sidebar.text_input("DB Password", "admin", type="password"),
    "host": st.sidebar.text_input("DB Host", "localhost"),
    "port": st.sidebar.text_input("DB Port", "5432")
}
ADJUDICATOR_NAME = st.sidebar.text_input("Your Name (Master)", "master_annotator")

st.sidebar.header("📂 File Paths")
# Default assumes 'outputs' is in the current working directory
# default_path = os.path.join(os.getcwd(), "outputs")
KEYFRAMES_ROOT_DIR = r"E:\ava-ui\proposal_generation_pipeline\proposal_generation_pipeline\outputs"

ATTRIBUTE_NAMES = list(ATTRIBUTE_DEFINITIONS.keys())


# --- Helper Functions ---
def get_db_connection(db_params):
    try:
        return psycopg2.connect(**db_params)
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None


def run_db_query(db_params, query, params=None, fetch_type="all"):
    conn = get_db_connection(db_params)
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if fetch_type == "all":
                result = cur.fetchall()
            elif fetch_type == "one":
                result = cur.fetchone()
            else:
                result = None
            conn.commit()
        conn.close()
        return result
    return None


# --- Project Selection Logic ---
conn = get_db_connection(db_params)
selected_project_id = None

if conn:
    st.sidebar.divider()
    st.sidebar.header("🗂️ Project Selection")
    # Fetch projects from DB
    projects = run_db_query(db_params, "SELECT project_id, name FROM projects ORDER BY project_id DESC")

    if projects:
        proj_options = {p['project_id']: f"ID {p['project_id']}: {p['name']}" for p in projects}
        selected_project_id = st.sidebar.selectbox(
            "Select Project to QC",
            options=list(proj_options.keys()),
            format_func=lambda x: proj_options[x]
        )
        st.sidebar.success(f"Active Project: {selected_project_id}")
    else:
        st.sidebar.warning("No projects found in database.")
        st.stop()


# --- Visualization Helpers ---
def draw_box_on_image(image_path, box, color=(0, 255, 0), label=None):
    """Draws a single box for audit."""
    if not os.path.exists(image_path): return None
    img = cv2.imread(image_path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    x1, y1, x2, y2 = int(box['xtl']), int(box['ytl']), int(box['xbr']), int(box['ybr'])
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    if label: cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img


def draw_comparison_image(image_path, annotations_a, annotations_b, assignee_a, assignee_b):
    """Draws boxes from two annotators for adjudication."""
    if not os.path.exists(image_path): return None
    img = cv2.imread(image_path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Annotator A (Green)
    for ann in annotations_a:
        x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, f"ID:{ann['person_id']} ({assignee_a})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 2)
    # Annotator B (Red)
    for ann in annotations_b:
        x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
        cv2.rectangle(img, (x1 + 3, y1 + 3), (x2 - 3, y2 - 3), (255, 0, 0), 2)
        cv2.putText(img, f"ID:{ann['person_id']} ({assignee_b})", (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 0, 0), 2)
    return img


def get_batch_folder_name(task_name, root_dir):
    """Finds the actual folder name on disk."""
    existing_batches = []
    if os.path.exists(root_dir):
        existing_batches = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

    for batch in existing_batches:
        if task_name.startswith(batch): return batch

    if '_' in task_name: return '_'.join(task_name.split('_')[:-1])
    return "Unknown_Batch"


def get_task_data_robust(db_params, root_dir, project_id):
    """Fetches all tasks for PROJECT and intelligently pairs them."""
    tasks = run_db_query(db_params,
                         "SELECT task_id, name, assignee, qc_status, project_id FROM tasks WHERE project_id = %s ORDER BY name",
                         (project_id,)
                         )

    overlap_pairs = []
    solo_tasks_by_annotator = defaultdict(list)
    tasks_by_batch = defaultdict(list)

    for task in tasks:
        batch_name = get_batch_folder_name(task['name'], root_dir)
        if batch_name == "Unknown_Batch" and len(task['name']) < 5:
            batch_name = "Test_Batch_Generic"
        tasks_by_batch[batch_name].append(task)

    for batch_name, task_list in tasks_by_batch.items():
        pending_adj = [t for t in task_list if t['qc_status'] == 'pending_adjudication']

        for i in range(0, len(pending_adj), 2):
            if i + 1 < len(pending_adj):
                t1, t2 = pending_adj[i], pending_adj[i + 1]
                overlap_pairs.append({
                    "task_id_A": t1['task_id'], "task_id_B": t2['task_id'],
                    "name_A": t1['name'], "name_B": t2['name'],
                    "assignee_A": t1['assignee'], "assignee_B": t2['assignee'],
                    "clip_name": batch_name, "project_id": t1['project_id'],
                    "status": "Pending Review"
                })

        pending_solo = [t for t in task_list if t['qc_status'] == 'pending']
        for t in pending_solo:
            solo_tasks_by_annotator[t['assignee']].append(t)

    return overlap_pairs, solo_tasks_by_annotator


def save_golden_annotation(db_params, project_id, task_id_a, task_id_b, keyframe, person_id, xtl, ytl, xbr, ybr,
                           attributes, adjudicator):
    query = """
            INSERT INTO golden_annotations
            (original_project_id, original_task_id_A, original_task_id_B, keyframe_name, person_id, xtl, ytl, xbr, ybr, \
             attributes, adjudicated_by, adjudicated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, \
                    CURRENT_TIMESTAMP) ON CONFLICT (keyframe_name, person_id) DO \
            UPDATE SET
                attributes = EXCLUDED.attributes, adjudicated_by = EXCLUDED.adjudicated_by, adjudicated_at = CURRENT_TIMESTAMP; \
            """
    run_db_query(db_params, query,
                 (project_id, task_id_a, task_id_b, keyframe, person_id, xtl, ytl, xbr, ybr, json.dumps(attributes),
                  adjudicator), fetch_type=None)


def get_annotations_for_adjudication(db_params, task_id_a, task_id_b, keyframe):
    query = """
    (SELECT task_id, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s)
    UNION ALL
    (SELECT task_id, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s);
    """
    return run_db_query(db_params, query, (task_id_a, keyframe, task_id_b, keyframe))


def get_common_keyframes(db_params, task_id_a, task_id_b):
    query = """
            SELECT keyframe_name \
            FROM annotations \
            WHERE task_id = %s
            INTERSECT
            SELECT keyframe_name \
            FROM annotations \
            WHERE task_id = %s; \
            """
    results = run_db_query(db_params, query, (task_id_a, task_id_b))
    return [row['keyframe_name'] for row in results]


# --- Navigation ---
page = st.sidebar.radio("Navigation",
                        ["Adjudication Queue (Conflicts)", "Blind Audit Queue (Random Check)",
                         "Annotator Calibration (Metrics)", "Bulk Approval", "Dataset Generation"]
                        )

if not selected_project_id:
    st.warning("Please select a project from the sidebar.")
    st.stop()

# ==============================================================================
# 1. ADJUDICATION QUEUE (Resolving Conflicts)
# ==============================================================================
if page == "Adjudication Queue (Conflicts)":
    st.header(f"⚔️ Adjudication Queue (Project {selected_project_id})")
    overlap_pairs, _ = get_task_data_robust(db_params, KEYFRAMES_ROOT_DIR, selected_project_id)

    if not overlap_pairs:
        st.success("No overlap tasks are currently pending review for this project.")
    else:
        df = pd.DataFrame(overlap_pairs)
        st.dataframe(df[['clip_name', 'assignee_A', 'assignee_B', 'status']], use_container_width=True)

        pair_idx = st.selectbox("Select Pair:", df.index, format_func=lambda
            x: f"{df.iloc[x]['clip_name']} ({df.iloc[x]['name_A']} vs {df.iloc[x]['name_B']})")
        if pair_idx is not None:
            pair = df.iloc[pair_idx]
            task_id_a = int(pair['task_id_A'])
            task_id_b = int(pair['task_id_B'])
            project_id = int(pair['project_id'])

            common_keyframes = get_common_keyframes(db_params, task_id_a, task_id_b)
            if not common_keyframes:
                st.warning("These tasks have no keyframes in common.")
                st.stop()

            keyframe = st.selectbox("Select Keyframe:", common_keyframes)

            if keyframe:
                annotations = get_annotations_for_adjudication(db_params, task_id_a, task_id_b, keyframe)

                batch_name = pair['clip_name']
                img_path = os.path.join(KEYFRAMES_ROOT_DIR, batch_name, "keyframes", keyframe)
                # Fallback for test batches
                if batch_name == "Test_Batch_Generic" and not os.path.exists(img_path):
                    img_path = os.path.join(KEYFRAMES_ROOT_DIR, "keyframes", keyframe)

                ann_a = [a for a in annotations if a['task_id'] == task_id_a]
                ann_b = [a for a in annotations if a['task_id'] == task_id_b]

                img = draw_comparison_image(img_path, ann_a, ann_b, pair['assignee_A'], pair['assignee_B'])
                if img is not None:
                    st.image(img, caption="Comparison", use_container_width=True)
                else:
                    st.error(f"Image not found at: {img_path}")

                st.subheader("Resolve Conflict")
                ann_a_dict = {a['person_id']: a for a in ann_a}
                ann_b_dict = {a['person_id']: a for a in ann_b}
                all_person_ids = sorted(list(set(ann_a_dict.keys()) | set(ann_b_dict.keys())))

                for pid in all_person_ids:
                    with st.expander(f"Person {pid}", expanded=True):
                        col1, col2, col3 = st.columns(3)
                        da = next((a for a in ann_a if a['person_id'] == pid), {})
                        db = next((a for a in ann_b if a['person_id'] == pid), {})

                        with col1:
                            st.info("A"); st.json(da.get('attributes', {}))
                        with col2:
                            st.info("B"); st.json(db.get('attributes', {}))
                        with col3:
                            st.markdown("Golden")
                            tmpl = da if da else db
                            if tmpl:
                                with st.form(f"adj_{keyframe}_{pid}"):
                                    final_attrs = {}
                                    for k, v in ATTRIBUTE_DEFINITIONS.items():
                                        curr = tmpl['attributes'].get(k, v.get('default', ''))
                                        try:
                                            idx = v['options'].index(curr)
                                        except ValueError:
                                            idx = 0
                                        final_attrs[k] = st.selectbox(k, v['options'], index=idx)
                                    if st.form_submit_button("Save Golden"):
                                        save_golden_annotation(
                                            db_params, project_id, task_id_a, task_id_b,
                                            keyframe, int(pid), tmpl['xtl'], tmpl['ytl'], tmpl['xbr'], tmpl['ybr'],
                                            final_attrs, ADJUDICATOR_NAME
                                        )
                                        st.success("Saved")

            st.divider()
            if st.button("✅ Mark Batch Complete"):
                run_db_query(db_params, "UPDATE tasks SET qc_status='review_complete' WHERE task_id IN (%s, %s)",
                             (task_id_a, task_id_b), fetch_type=None)
                st.success(f"Batch {pair['clip_name']} marked as complete!")
                st.rerun()

# ==============================================================================
# 2. BLIND AUDIT QUEUE (Zero Tolerance)
# ==============================================================================
elif page == "Blind Audit Queue (Random Check)":
    st.header(f"🕵️‍♀️ Blind Audit Queue (Project {selected_project_id})")
    st.info("We audit 60% of agreed clips. To claim <5% error with 95% confidence, we must have **0 overturns**.")

    tasks = run_db_query(db_params,
                         "SELECT task_id, name, qc_status FROM tasks WHERE qc_status = 'pending_audit' AND project_id = %s ORDER BY name",
                         (selected_project_id,))

    if not tasks:
        st.success("No audits pending for this project.")

        # --- RESET LOGIC ---
        # Check for rejected tasks to offer a reset (useful for testing)
        rejected_tasks = run_db_query(db_params,
                                      "SELECT COUNT(*) FROM tasks WHERE qc_status = 'rejected' AND project_id = %s",
                                      (selected_project_id,), fetch_type="one")
        if rejected_tasks and rejected_tasks[0] > 0:
            st.error(f"⚠️ Found {rejected_tasks[0]} REJECTED tasks in this project.")
            if st.button("♻️ RESET Rejected Tasks (For Testing)"):
                # Reset status
                run_db_query(db_params,
                             "UPDATE tasks SET qc_status = 'pending_audit' WHERE qc_status = 'rejected' AND project_id = %s",
                             (selected_project_id,), fetch_type=None)
                # Optional: Clear previous audit records for these tasks to reset the score
                # This requires joining tables, simplified here to just resetting status
                st.success("Tasks reset to 'pending_audit'.")
                st.rerun()
    else:
        current_batch_name = get_batch_folder_name(tasks[0]['name'], KEYFRAMES_ROOT_DIR)
        st.subheader(f"Auditing Batch: {current_batch_name}")

        batch_tasks = [t for t in tasks if get_batch_folder_name(t['name'], KEYFRAMES_ROOT_DIR) == current_batch_name]
        batch_task_ids = tuple([t['task_id'] for t in batch_tasks])

        if batch_task_ids:
            pending_audits_raw = run_db_query(db_params, "SELECT * FROM audits WHERE is_overturn IS NULL")
            pending_audits = [a for a in pending_audits_raw if a['task_id'] in batch_task_ids]
        else:
            pending_audits = []

        all_audits_raw = run_db_query(db_params,
                                      "SELECT a.is_overturn, t.name FROM audits a JOIN tasks t ON a.task_id = t.task_id WHERE a.is_overturn IS NOT NULL AND t.project_id = %s",
                                      (selected_project_id,))
        batch_completed_audits = [a for a in all_audits_raw if current_batch_name in a['name']]

        if batch_completed_audits:
            total = len(batch_completed_audits)
            errors = sum(1 for r in batch_completed_audits if r['is_overturn'])
            accuracy = ((total - errors) / total) * 100

            col1, col2, col3 = st.columns(3)
            col1.metric("Audited So Far", total)
            col2.metric("Errors Found", errors)
            col3.metric("Accuracy", f"{accuracy:.1f}%")

            if errors > 0:
                st.error(f"❌ **ZERO TOLERANCE FAILURE**: Found {errors} error(s). Batch rejected.")

        if not pending_audits:
            st.success(f"Audit for batch {current_batch_name} complete!")
            if batch_completed_audits and errors == 0:
                if st.button("Finalize Approval"):
                    run_db_query(db_params,
                                 "UPDATE tasks SET qc_status='approved' WHERE qc_status='pending_audit' AND name LIKE %s AND project_id=%s",
                                 (f"{current_batch_name}%", selected_project_id), fetch_type=None)
                    st.balloons()
                    st.rerun()
            elif batch_completed_audits and errors > 0:
                if st.button("Reject Batch"):
                    run_db_query(db_params,
                                 "UPDATE tasks SET qc_status='rejected' WHERE (qc_status='pending_audit' OR qc_status='approved') AND name LIKE %s AND project_id=%s",
                                 (f"{current_batch_name}%", selected_project_id), fetch_type=None)
                    st.rerun()
        else:
            item = pending_audits[0]
            img_path = os.path.join(KEYFRAMES_ROOT_DIR, current_batch_name, "keyframes", item['keyframe_name'])

            col1, col2 = st.columns([2, 1])
            with col1:
                ann_res = run_db_query(db_params,
                                       "SELECT xtl, ytl, xbr, ybr FROM annotations WHERE task_id=%s AND keyframe_name=%s AND person_id=%s",
                                       (item['task_id'], item['keyframe_name'], item['person_id']), fetch_type="one")
                if ann_res:
                    img = draw_box_on_image(img_path, ann_res, color=(255, 255, 0), label="Person")
                    if img is not None:
                        st.image(img, use_container_width=True)
                    else:
                        st.error(f"Image missing at {img_path}")
            with col2:
                st.markdown(f"### Audit Person {item['person_id']}")
                with st.form("audit"):
                    audit_attrs = {}
                    for k, v in ATTRIBUTE_DEFINITIONS.items():
                        audit_attrs[k] = st.selectbox(k, v['options'],
                                                      index=v['options'].index(v.get('default', v['options'][0])))
                    if st.form_submit_button("Submit"):
                        orig = item['original_consensus_attributes']
                        overturn = (audit_attrs != orig)
                        run_db_query(db_params,
                                     "UPDATE audits SET auditor_attributes=%s, is_overturn=%s, auditor_id=%s WHERE audit_id=%s",
                                     (json.dumps(audit_attrs), overturn, ADJUDICATOR_NAME, item['audit_id']),
                                     fetch_type=None)
                        st.rerun()

# ==============================================================================
# 3. METRICS & CALIBRATION
# ==============================================================================
elif page == "Annotator Calibration (Metrics)":
    st.header(f"📊 Annotator Metrics (Project {selected_project_id})")

    tasks = run_db_query(db_params,
                         "SELECT task_id, name, assignee FROM tasks WHERE qc_status = 'review_complete' AND project_id = %s",
                         (selected_project_id,))
    if not tasks:
        st.warning("No adjudicated tasks available for this project.")
    else:
        annotators = sorted(list(set(t['assignee'] for t in tasks)))
        user = st.selectbox("Annotator", annotators)

        if st.button("Calculate Score"):
            user_tasks = [t['task_id'] for t in tasks if t['assignee'] == user]
            qc_service = QCService(db_params)
            all_scores = defaultdict(list)

            with st.spinner("Calculating..."):
                for tid in user_tasks:
                    scores = qc_service.calculate_kappa_vs_golden(tid, ATTRIBUTE_NAMES)
                    for k, v in scores.items(): all_scores[k].append(v)

            avg = {k: sum(v) / len(v) for k, v in all_scores.items()}
            st.dataframe(pd.DataFrame.from_dict(avg, orient='index', columns=['Kappa']))
            final_avg = sum(avg.values()) / len(avg)
            st.metric("Average Kappa", f"{final_avg:.3f}")
            if final_avg >= 0.85:
                st.success("Calibrated!")
            else:
                st.error("Needs Training")

# ==============================================================================
# 4. BULK APPROVAL & DATASET
# ==============================================================================
elif page == "Bulk Approval":
    st.header(f"Bulk Approval (Project {selected_project_id})")
    _, solo_map = get_task_data_robust(db_params, KEYFRAMES_ROOT_DIR, selected_project_id)
    if not solo_map: st.success("No pending solo tasks.")
    for user, tasks in solo_map.items():
        if st.button(f"Approve {len(tasks)} tasks for {user}"):
            tids = [t['task_id'] for t in tasks]
            run_db_query(db_params, "UPDATE tasks SET qc_status='approved' WHERE task_id = ANY(%s)", (tids,),
                         fetch_type=None)
            st.success("Approved!")
            st.rerun()

elif page == "Dataset Generation":
    st.header(f"Dataset Generation (Project {selected_project_id})")
    manifest = st.text_input("Manifest Path", r"F:\ava_kinetics - Copy\AVA_kinetics_multiAnnotator_pipeline\proposal_generation_pipeline\proposal_generation_pipeline\outputs\factory_batch_01\manifest.json")
    outfile = st.text_input("Output CSV", "final_ava.csv")

    if st.button("Generate"):
        if not os.path.exists(manifest):
            st.error("Manifest not found")
        else:
            try:
                gen = DatasetGenerator(db_params, manifest)
                # IMPORTANT: In a real scenario, you should filter the generator by project_id too.
                # For prototype, it filters by 'approved' status, which is sufficient if you work on one project at a time.
                gen.generate_ava_csv(outfile)
                st.success("Done!")
            except Exception as e:
                st.error(f"Error: {e}")