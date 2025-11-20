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

# Import services
try:
    from services.dataset_generator import DatasetGenerator, ATTRIBUTE_DEFINITIONS
    from services.qc_service import QCService
except ImportError:
    st.error(
        "Could not import services. Make sure 'dataset_generator.py' and 'qc_service.py' are in the 'tools/' directory.")
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
KEYFRAMES_ROOT_DIR = st.sidebar.text_input("Root Directory for Batches", "outputs")


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


def draw_box_on_image(image_path, box, color=(0, 255, 0), label=None):
    """Draws a single box for audit or comparison."""
    if not os.path.exists(image_path): return None
    img = cv2.imread(image_path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    x1, y1, x2, y2 = int(box['xtl']), int(box['ytl']), int(box['xbr']), int(box['ybr'])
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    if label:
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img


def draw_comparison_image(image_path, annotations_a, annotations_b, assignee_a, assignee_b):
    if not os.path.exists(image_path):
        return None

    img = cv2.imread(image_path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    for ann in annotations_a:
        x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, f"ID:{ann['person_id']} ({assignee_a})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 2)

    for ann in annotations_b:
        x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
        cv2.rectangle(img, (x1 + 2, y1 + 2), (x2 - 2, y2 - 2), (255, 0, 0), 2)
        cv2.putText(img, f"ID:{ann['person_id']} ({assignee_b})", (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 0, 0), 2)

    return img


def get_batch_folder_name(task_name, root_dir):
    """Tries to find the actual folder name on disk corresponding to the task."""
    existing_batches = []
    if os.path.exists(root_dir):
        existing_batches = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

    for batch in existing_batches:
        if task_name.startswith(batch):
            return batch
    return '_'.join(task_name.split('_')[:-1])


def get_annotations_for_adjudication(db_params, task_id_a, task_id_b, keyframe):
    query = """
    (SELECT task_id, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s)
    UNION ALL
    (SELECT task_id, person_id, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s);
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


def save_golden_annotation(db_params, project_id, task_id_a, task_id_b, keyframe, person_id, xtl, ytl, xbr, ybr,
                           attributes, adjudicator):
    query = """
            INSERT INTO golden_annotations
            (original_project_id, original_task_id_A, original_task_id_B, keyframe_name, person_id, xtl, ytl, xbr, ybr, \
             attributes, adjudicated_by, adjudicated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, \
                    CURRENT_TIMESTAMP) ON CONFLICT (keyframe_name, person_id) DO \
            UPDATE SET
                attributes = EXCLUDED.attributes, \
                adjudicated_by = EXCLUDED.adjudicated_by, \
                adjudicated_at = CURRENT_TIMESTAMP; \
            """
    run_db_query(db_params, query,
                 (project_id, task_id_a, task_id_b, keyframe, person_id, xtl, ytl, xbr, ybr, json.dumps(attributes),
                  adjudicator), fetch_type=None)


def get_task_data(db_params, root_dir):
    tasks = run_db_query(db_params, "SELECT task_id, name, assignee, qc_status, project_id FROM tasks ORDER BY name")
    overlap_pairs = []
    tasks_by_base_name = defaultdict(list)
    solo_tasks_by_annotator = defaultdict(list)

    # Cache folder list
    existing_batches = []
    if os.path.exists(root_dir):
        existing_batches = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

    for task in tasks:
        matched_batch = None
        for batch in existing_batches:
            if task['name'].startswith(batch):
                matched_batch = batch
                break
        if not matched_batch:
            matched_batch = '_'.join(task['name'].split('_')[:-1])

        tasks_by_base_name[matched_batch].append(task)

    for base_name, task_list in tasks_by_base_name.items():
        pending_tasks = [t for t in task_list if t['qc_status'] == 'pending']
        if len(pending_tasks) == 2:
            overlap_pairs.append({
                "task_id_A": pending_tasks[0]['task_id'],
                "task_id_B": pending_tasks[1]['task_id'],
                "name_A": pending_tasks[0]['name'],
                "name_B": pending_tasks[1]['name'],
                "assignee_A": pending_tasks[0]['assignee'],
                "assignee_B": pending_tasks[1]['assignee'],
                "clip_name": base_name,
                "project_id": pending_tasks[0]['project_id'],
                "status": "Pending Review"
            })
        elif len(pending_tasks) == 1:
            solo_tasks_by_annotator[pending_tasks[0]['assignee']].append(pending_tasks[0])
    return overlap_pairs, solo_tasks_by_annotator


# --- Navigation ---
page = st.sidebar.radio("Navigation",
                        ["Adjudication Queue (Conflicts)", "Blind Audit Queue (Random Check)",
                         "Annotator Calibration (Metrics)", "Bulk Approval", "Dataset Generation"]
                        )

if not get_db_connection(db_params):
    st.stop()

ATTRIBUTE_NAMES = list(ATTRIBUTE_DEFINITIONS.keys())

# ==============================================================================
# 1. ADJUDICATION QUEUE (Resolving Conflicts)
# ==============================================================================
if page == "Adjudication Queue (Conflicts)":
    st.header("⚔️ Adjudication Queue")
    st.info("Tasks where annotators DISAGREED. Review and set the 'Golden' truth.")

    # Fetch tasks marked as 'pending_adjudication'
    tasks = run_db_query(db_params,
                         "SELECT task_id, name, assignee, qc_status, project_id FROM tasks WHERE qc_status = 'pending_adjudication' ORDER BY name")

    if not tasks:
        st.success("No conflicts pending adjudication.")
    else:
        # Group by batch manually since we aren't using get_task_data here
        tasks_by_batch = defaultdict(list)
        existing_batches = [d for d in os.listdir(KEYFRAMES_ROOT_DIR) if
                            os.path.isdir(os.path.join(KEYFRAMES_ROOT_DIR, d))] if os.path.exists(
            KEYFRAMES_ROOT_DIR) else []

        for task in tasks:
            matched = next((b for b in existing_batches if task['name'].startswith(b)),
                           '_'.join(task['name'].split('_')[:-1]))
            tasks_by_batch[matched].append(task)

        overlap_pairs = []
        for batch_name, task_list in tasks_by_batch.items():
            if len(task_list) >= 2:
                for i in range(0, len(task_list), 2):
                    if i + 1 < len(task_list):
                        t1, t2 = task_list[i], task_list[i + 1]
                        overlap_pairs.append({
                            "task_id_A": t1['task_id'], "task_id_B": t2['task_id'],
                            "name_A": t1['name'], "name_B": t2['name'],
                            "assignee_A": t1['assignee'], "assignee_B": t2['assignee'],
                            "clip_name": batch_name, "project_id": t1['project_id']
                        })

        if not overlap_pairs:
            st.warning("Found pending adjudication tasks but couldn't pair them up. Check data integrity.")
        else:
            df = pd.DataFrame(overlap_pairs)
            st.dataframe(df[['clip_name', 'assignee_A', 'assignee_B']], use_container_width=True)

            pair_to_review_idx = st.selectbox("Select a clip to review:", df.index,
                                              format_func=lambda x: df.iloc[x]['clip_name'])

            if pair_to_review_idx is not None:
                pair = df.iloc[pair_to_review_idx]
                st.subheader(f"Reviewing: {pair['clip_name']}")

                common_keyframes = get_common_keyframes(db_params, pair['task_id_A'], pair['task_id_B'])
                if not common_keyframes:
                    st.warning("These tasks have no keyframes in common.")
                    st.stop()

                keyframe = st.selectbox("Select a keyframe to adjudicate:", common_keyframes)

                if keyframe:
                    annotations = get_annotations_for_adjudication(db_params, pair['task_id_A'], pair['task_id_B'],
                                                                   keyframe)
                    img_path = os.path.join(KEYFRAMES_ROOT_DIR, pair['clip_name'], "keyframes", keyframe)

                    ann_a_data = [a for a in annotations if a['task_id'] == pair['task_id_A']]
                    ann_b_data = [a for a in annotations if a['task_id'] == pair['task_id_B']]

                    annotated_img = draw_comparison_image(img_path, ann_a_data, ann_b_data, pair['assignee_A'],
                                                          pair['assignee_B'])

                    if annotated_img is not None:
                        st.image(annotated_img, caption=f"Green: {pair['assignee_A']} | Red: {pair['assignee_B']}",
                                 use_container_width=True)
                    else:
                        st.error(f"Image not found: {img_path}")

                    st.write("---")
                    st.subheader("Resolve Conflict")

                    ann_a_dict = {a['person_id']: a for a in ann_a_data}
                    ann_b_dict = {a['person_id']: a for a in ann_b_data}
                    all_person_ids = sorted(list(set(ann_a_dict.keys()) | set(ann_b_dict.keys())))

                    for pid in all_person_ids:
                        with st.expander(f"Person {pid}", expanded=True):
                            col1, col2, col3 = st.columns(3)
                            data_a = ann_a_dict.get(pid)
                            data_b = ann_b_dict.get(pid)

                            with col1:
                                st.markdown(f"**{pair['assignee_A']}**")
                                if data_a: st.json(data_a['attributes'])
                            with col2:
                                st.markdown(f"**{pair['assignee_B']}**")
                                if data_b: st.json(data_b['attributes'])
                            with col3:
                                st.markdown("**Final Verdict**")
                                template = data_a if data_a else data_b
                                if template:
                                    with st.form(
                                            f"adj_{selected_frame if 'selected_frame' in locals() else keyframe}_{pid}"):  # Fallback keyframe var
                                        final_attrs = {}
                                        for k, v in ATTRIBUTE_DEFINITIONS.items():
                                            curr = template['attributes'].get(k, v['default'])
                                            idx = v['options'].index(curr) if curr in v['options'] else 0
                                            final_attrs[k] = st.selectbox(k, v['options'], index=idx)

                                        if st.form_submit_button("💾 Save Golden Decision"):
                                            save_golden_annotation(
                                                db_params, pair['project_id'], pair['task_id_A'], pair['task_id_B'],
                                                keyframe, pid, template['xtl'], template['ytl'], template['xbr'],
                                                template['ybr'],
                                                final_attrs, ADJUDICATOR_NAME
                                            )
                                            st.success("Saved!")

                st.divider()
                if st.button("✅ Mark Batch as 'Review Complete'", type="primary"):
                    run_db_query(db_params, "UPDATE tasks SET qc_status = 'review_complete' WHERE task_id IN (%s, %s)",
                                 (pair['task_id_A'], pair['task_id_B']), fetch_type=None)
                    st.success(f"Batch {pair['clip_name']} marked as complete!")
                    st.rerun()

# ==============================================================================
# 2. BLIND AUDIT QUEUE (Zero Tolerance)
# ==============================================================================
elif page == "Blind Audit Queue (Random Check)":
    st.header("🕵️‍♀️ Blind Audit Queue (Zero Tolerance)")
    st.info("We audit 60% of agreed clips. To claim <5% error with 95% confidence, we must have **0 overturns**.")

    tasks = run_db_query(db_params,
                         "SELECT task_id, name, qc_status FROM tasks WHERE qc_status = 'pending_audit' ORDER BY name")

    if not tasks:
        st.success("No audits pending.")
    else:
        current_batch_name = get_batch_folder_name(tasks[0]['name'], KEYFRAMES_ROOT_DIR)
        st.subheader(f"Auditing Batch: {current_batch_name}")

        batch_tasks = [t for t in tasks if get_batch_folder_name(t['name'], KEYFRAMES_ROOT_DIR) == current_batch_name]
        batch_task_ids = tuple([t['task_id'] for t in batch_tasks])

        if batch_task_ids:
            # Fetch pending audits for this batch
            pending_audits_raw = run_db_query(db_params, "SELECT * FROM audits WHERE is_overturn IS NULL")
            pending_audits = [a for a in pending_audits_raw if a['task_id'] in batch_task_ids]
        else:
            pending_audits = []

        # Calculate batch stats so far
        all_audits_raw = run_db_query(db_params,
                                      "SELECT a.is_overturn, t.name FROM audits a JOIN tasks t ON a.task_id = t.task_id WHERE a.is_overturn IS NOT NULL")
        batch_completed_audits = [a for a in all_audits_raw if current_batch_name in a['name']]

        if batch_completed_audits:
            total_audited = len(batch_completed_audits)
            errors = sum(1 for r in batch_completed_audits if r['is_overturn'])
            accuracy = ((total_audited - errors) / total_audited) * 100

            col1, col2, col3 = st.columns(3)
            col1.metric("Audited So Far", total_audited)
            col2.metric("Errors Found", errors)
            col3.metric("Accuracy", f"{accuracy:.1f}%")

            if errors > 0:
                st.error(f"❌ **ZERO TOLERANCE FAILURE**: Found {errors} error(s). Cannot claim <5% error rate.")

        if not pending_audits:
            st.success(f"Audit for batch {current_batch_name} complete!")

            if batch_completed_audits:
                total = len(batch_completed_audits)
                errors = sum(1 for r in batch_completed_audits if r['is_overturn'])

                # ZERO TOLERANCE LOGIC
                if errors == 0:
                    st.success("✅ **PASSED (0 Errors)**. We are 95% confident the error rate is <5%.")
                    if st.button("Finalize Approval"):
                        run_db_query(db_params,
                                     "UPDATE tasks SET qc_status = 'approved' WHERE qc_status = 'pending_audit' AND name LIKE %s",
                                     (f"{current_batch_name}%",), fetch_type=None)
                        st.balloons()
                        st.rerun()
                else:
                    st.error(f"❌ **FAILED**. Found {errors} errors. Batch must be rejected.")
                    if st.button("Reject Batch"):
                        # Reject EVERYTHING in the batch
                        run_db_query(db_params,
                                     "UPDATE tasks SET qc_status = 'rejected' WHERE (qc_status = 'pending_audit' OR qc_status = 'approved') AND name LIKE %s",
                                     (f"{current_batch_name}%",), fetch_type=None)
                        st.rerun()
            else:
                st.warning("No completed audits found.")
        else:
            # Display the audit item
            item = pending_audits[0]
            img_path = os.path.join(KEYFRAMES_ROOT_DIR, current_batch_name, "keyframes", item['keyframe_name'])

            col1, col2 = st.columns([2, 1])
            with col1:
                # Blind drawing
                ann_res = run_db_query(db_params,
                                       "SELECT xtl, ytl, xbr, ybr FROM annotations WHERE task_id=%s AND keyframe_name=%s AND person_id=%s",
                                       (item['task_id'], item['keyframe_name'], item['person_id']), fetch_type="one")
                if ann_res:
                    img = draw_box_on_image(img_path, ann_res, color=(255, 255, 0), label=f"Person {item['person_id']}")
                    if img is not None:
                        st.image(img, use_container_width=True)
                    else:
                        st.error(f"Image not found: {img_path}")
                else:
                    st.error("Could not find box.")

            with col2:
                st.markdown(f"### Audit: Person {item['person_id']}")
                st.info("Select correct labels. (Originals hidden)")

                with st.form("audit_form"):
                    audit_attrs = {}
                    for k, v in ATTRIBUTE_DEFINITIONS.items():
                        audit_attrs[k] = st.selectbox(k, v['options'], index=v['options'].index(v['default']))

                    if st.form_submit_button("Submit Audit"):
                        original_attrs = item['original_consensus_attributes']
                        is_overturn = (audit_attrs != original_attrs)

                        run_db_query(db_params,
                                     "UPDATE audits SET auditor_attributes = %s, is_overturn = %s, auditor_id = %s WHERE audit_id = %s",
                                     (json.dumps(audit_attrs), is_overturn, ADJUDICATOR_NAME, item['audit_id']),
                                     fetch_type=None
                                     )

                        if is_overturn:
                            st.toast("⚠️ Error Found!", icon="❌")
                        else:
                            st.toast("✅ Verified", icon="✅")
                        st.rerun()

# ==============================================================================
# 3. METRICS & DATASET (Simplified)
# ==============================================================================
elif page == "Annotator Calibration (Metrics)":
    st.header("Annotator Calibration (Metrics)")

    tasks = run_db_query(db_params, "SELECT task_id, name, assignee FROM tasks WHERE qc_status = 'review_complete'")
    if not tasks:
        st.warning("No tasks are 'review_complete'. Adjudicate tasks first.")
        st.stop()

    annotators = sorted(list(set(t['assignee'] for t in tasks)))
    annotator_to_check = st.selectbox("Select an annotator to calibrate:", annotators)

    if st.button(f"Calculate Calibration Score for {annotator_to_check}"):
        annotator_tasks = [t['task_id'] for t in tasks if t['assignee'] == annotator_to_check]
        qc_service = QCService(db_params)
        all_scores = defaultdict(list)

        with st.spinner(f"Calculating scores..."):
            for task_id in annotator_tasks:
                scores = qc_service.calculate_kappa_vs_golden(task_id, ATTRIBUTE_NAMES)
                for attr, score in scores.items():
                    all_scores[attr].append(score)

        st.subheader(f"Calibration Report: {annotator_to_check}")
        avg_scores = {attr: (sum(s_list) / len(s_list)) for attr, s_list in all_scores.items()}
        st.dataframe(
            pd.DataFrame.from_dict(avg_scores, orient='index', columns=['Average Kappa']).style.format("{:.3f}"))
        st.metric("Overall Average Kappa", f"{sum(avg_scores.values()) / len(avg_scores):.3f}")

elif page == "Bulk Approval":
    st.header("Bulk Approval (Solo Tasks)")
    _, solo_tasks_by_annotator = get_task_data(db_params, KEYFRAMES_ROOT_DIR)

    if not solo_tasks_by_annotator:
        st.success("No solo tasks are pending approval.")
    else:
        for annotator, tasks in solo_tasks_by_annotator.items():
            with st.expander(f"Pending tasks for {annotator} ({len(tasks)} tasks)"):
                st.dataframe(pd.DataFrame(tasks))
                if st.button(f"✅ Approve all {len(tasks)} tasks for {annotator}", key=annotator):
                    task_ids = [t['task_id'] for t in tasks]
                    run_db_query(db_params, "UPDATE tasks SET qc_status = 'approved' WHERE task_id = ANY(%s)",
                                 (task_ids,), fetch_type=None)
                    st.success(f"Approved {len(task_ids)} tasks.")
                    st.rerun()

elif page == "Dataset Generation":
    st.header("Dataset Generation")
    manifest_path_str = st.text_input("Path to Master Manifest File", "outputs/factory_batch_01/manifest.json")
    output_filename = st.text_input("Output CSV Filename", "ava_kinetics_dataset_final.csv")

    if st.button("📊 Generate Final Dataset", type="primary"):
        manifest_path = Path(manifest_path_str)
        if not manifest_path.exists():
            st.error(f"Manifest file not found at: {manifest_path.resolve()}")
        else:
            with st.spinner("Generating dataset..."):
                try:
                    generator = DatasetGenerator(db_params, str(manifest_path))
                    generator.generate_ava_csv(output_filename)
                    st.success(f"✅ Dataset generation complete! File saved as: `{output_filename}`")
                except Exception as e:
                    st.error(f"An error occurred during dataset generation:")
                    st.exception(e)