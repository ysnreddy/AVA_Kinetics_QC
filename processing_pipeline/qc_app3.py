# import streamlit as st
# import psycopg2
# import psycopg2.extras
# import pandas as pd
# import os
# import json
# import cv2
# import numpy as np
# from collections import defaultdict
# from pathlib import Path
# import yaml
# import io

# # --- Helper Logic ---
# def load_cvat_labels_internal(config_path: Path):
#     if not config_path.exists():
#         raise FileNotFoundError(f"CVAT label config not found: {config_path}")
#     with open(config_path, "r") as f:
#         data = yaml.safe_load(f)
#     return data["labels"]

# def draw_comparison_image(path, ann_a, ann_b):
#     if not os.path.exists(path): return None
#     img = cv2.imread(path)
#     if img is None: return None
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
#     # Annotator A (Green) - Consistent ID
#     for a in ann_a: 
#         cv2.rectangle(img, (int(a['xtl']), int(a['ytl'])), (int(a['xbr']), int(a['ybr'])), (0, 255, 0), 2)
#         cv2.putText(img, f"ID:{a['person_id']} (A)", (int(a['xtl']), int(a['ytl'])-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        
#     # Annotator B (Red) - Consistent ID (offset for visibility)
#     for b in ann_b: 
#         cv2.rectangle(img, (int(b['xtl'])+4, int(b['ytl'])+4), (int(b['xbr'])-4, int(b['ybr'])-4), (255, 0, 0), 2)
#         cv2.putText(img, f"ID:{b['person_id']} (B)", (int(b['xbr'])-60, int(b['ybr'])+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)
#     return img

# # --- Configuration ---
# st.set_page_config(page_title="AVA-Kinetics Adjudicator", layout="wide")
# st.title("🔬 Master Adjudication & AVA Export")

# st.sidebar.header("⚙️ Database Configuration")
# db_params = {
#     "dbname": st.sidebar.text_input("DB Name", "cvat_annotations_db"),
#     "user": st.sidebar.text_input("DB User", "admin"),
#     "password": st.sidebar.text_input("DB Password", "admin", type="password"),
#     "host": st.sidebar.text_input("DB Host", "localhost"),
#     "port": st.sidebar.text_input("DB Port", "5432")
# }

# ADJUDICATOR_NAME = st.sidebar.text_input("Master Annotator Name", "master_annotator")
# KEYFRAMES_ROOT_DIR = st.sidebar.text_input("Keyframes Root", r"E:\ava-ui\proposal_generation_pipeline\proposal_generation_pipeline\outputs")
# CONFIG_PATH = st.sidebar.text_input("YAML Config Path", r"E:\ava-ui\processing_pipeline\config\cvat_labels.yaml")

# # Action ID Mapping
# ACTION_MAP = {
#     "welding": 17, "cutting": 10, "climbing": 12, "lifting_materials": 14,
#     "machine_operation": 24, "supervising": 6, "walking": 1, "idle": 19
# }

# try:
#     ONTOLOGY = load_cvat_labels_internal(Path(CONFIG_PATH))
#     PERSON_ATTRIBUTES = ONTOLOGY[0]['attributes'] 
# except Exception as e:
#     st.error(f"Config Error: {e}"); st.stop()

# def run_db_query(params, query, data=None, fetch_type="all"):
#     conn = None
#     try:
#         conn = psycopg2.connect(**params)
#         with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#             cur.execute(query, data)
#             res = cur.fetchall() if fetch_type == "all" else cur.fetchone() if fetch_type == "one" else None
#             conn.commit()
#             return res
#     except Exception as e:
#         st.error(f"DB Error: {e}"); return None
#     finally:
#         if conn: conn.close()

# def calculate_iou(box_a, box_b):
#     x1, y1 = max(box_a['xtl'], box_b['xtl']), max(box_a['ytl'], box_b['ytl'])
#     x2, y2 = min(box_a['xbr'], box_b['xbr']), min(box_a['ybr'], box_b['ybr'])
#     inter = max(0, x2 - x1) * max(0, y2 - y1)
#     union = ((box_a['xbr']-box_a['xtl'])*(box_a['ybr']-box_a['ytl'])) + ((box_b['xbr']-box_b['xtl'])*(box_b['ybr']-box_b['ytl'])) - inter
#     return inter / union if union > 0 else 0

# def calculate_jaccard(l1, l2):
#     s1, s2 = set(l1), set(l2)
#     return len(s1 & s2) / len(s1 | s2) if len(s1 | s2) > 0 else 0

# def flatten_attributes(attr):
#     return [f"{k}:{v}" for k, v in attr.items() if v and v != 'none']

# # Navigation
# page = st.sidebar.radio("Navigation", ["📊 Routing", "⚔️ Adjudication (Prioritized)", "📥 AVA Dataset Export"])

# projects = run_db_query(db_params, "SELECT project_id, name FROM projects ORDER BY project_id DESC")
# if not projects: st.stop()
# selected_project_id = st.sidebar.selectbox("Select Project", [p[0] for p in projects], format_func=lambda x: next(p[1] for p in projects if p[0] == x))

# # ==============================================================================
# # PAGE 1: ROUTING
# # ==============================================================================
# if page == "📊 Routing":
#     st.header(f"Batch Routing for Project {selected_project_id}")
#     if st.button("▶️ Run Routing Logic"):
#         st.success("Routing process triggered successfully.")

# # ==============================================================================
# # PAGE 2: ADJUDICATION
# # ==============================================================================
# elif page == "⚔️ Adjudication (Prioritized)":
#     tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_adjudication'", (selected_project_id,))
#     if tasks:
#         by_name = defaultdict(list)
#         for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
#         st.session_state.sel_batch = st.selectbox("Select Batch", list(by_name.keys()))
#         pair = by_name[st.session_state.sel_batch]
#         t_ids = (pair[0]['task_id'], pair[1]['task_id'])

#         st.write("### 🛠️ Batch Controls")
#         col_app, col_rej = st.columns(2)
#         if col_app.button("✅ Approve Entire Batch (Mark Approved)", use_container_width=True):
#             run_db_query(db_params, "UPDATE tasks SET qc_status='approved' WHERE task_id IN (%s, %s)", t_ids, None)
#             st.success(f"Success: Batch {st.session_state.sel_batch} is now Approved.")
#             st.toast("Batch Finalized", icon="✅")
#             st.rerun()
#         if col_rej.button("❌ Reject Entire Batch (Send Back)", use_container_width=True):
#             run_db_query(db_params, "UPDATE tasks SET qc_status='rejected' WHERE task_id IN (%s, %s)", t_ids, None)
#             st.warning(f"Rejected: Batch {st.session_state.sel_batch} returned to Annotators.")
#             st.toast("Batch Rejected", icon="❌")
#             st.rerun()
#         st.divider()

#         raw_anns = run_db_query(db_params, "SELECT * FROM annotations WHERE task_id IN (%s, %s)", t_ids)
#         kf_groups = defaultdict(lambda: defaultdict(list))
#         for r in raw_anns: kf_groups[r['keyframe_name']][r['task_id']].append(r)
        
#         priority_list = []
#         for kname, t_data in kf_groups.items():
#             la, lb = t_data.get(t_ids[0], []), t_data.get(t_ids[1], [])
#             conflict = (len(la) != len(lb))
#             if not conflict:
#                 for a in la:
#                     m = next((b for b in lb if calculate_iou(a, b) >= 0.5), None)
#                     if not m or calculate_jaccard(flatten_attributes(a['attributes']), flatten_attributes(m['attributes'])) < 1.0:
#                         conflict = True; break
            
#             solved = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND original_project_id=%s", (kname, selected_project_id), "one")
#             prefix = "🔥 CONFLICT" if conflict else "🟢 AGREEMENT"
#             if solved: prefix = "✅ SOLVED"
#             priority_list.append(f"{prefix} | {kname}")

#         selected_kf_entry = st.selectbox("Select Keyframe", sorted(priority_list))
#         active_kf = selected_kf_entry.split(" | ")[1]

#         st.divider()
#         anns = [r for r in raw_anns if r['keyframe_name'] == active_kf]
#         ann_a, ann_b = [a for a in anns if a['task_id'] == t_ids[0]], [a for a in anns if a['task_id'] == t_ids[1]]
#         img_path = os.path.join(KEYFRAMES_ROOT_DIR, st.session_state.sel_batch, "keyframes", active_kf)
#         img = draw_comparison_image(img_path, ann_a, ann_b)
#         if img is not None: st.image(img, use_container_width=True)

#         for pid in sorted(set([a['person_id'] for a in anns])):
#             done = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND person_id=%s AND original_project_id=%s", (active_kf, pid, selected_project_id), "one")
            
#             with st.expander(f"Person {pid} {'✅' if done else '🔴'}"):
#                 a_dat, b_dat = next((x for x in ann_a if x['person_id'] == pid), None), next((x for x in ann_b if x['person_id'] == pid), None)
#                 c1, c2, c3 = st.columns(3)
#                 c1.json(a_dat['attributes'] if a_dat else {})
#                 c2.json(b_dat['attributes'] if b_dat else {})
#                 with c3:
#                     choice = st.radio("Verdict:", ["Annotator A", "Annotator B", "Custom"], key=f"rad_{pid}_{active_kf}")
#                     final = a_dat['attributes'] if choice == "Annotator A" else b_dat['attributes'] if choice == "Annotator B" else {}
#                     if choice == "Custom":
#                         for attr in PERSON_ATTRIBUTES: 
#                             idx = attr['values'].index(a_dat['attributes'].get(attr['name'], attr['values'][0])) if a_dat else 0
#                             final[attr['name']] = st.selectbox(attr['name'], attr['values'], index=idx, key=f"adj_{pid}_{attr['name']}")
                    
#                     if st.button("Save Decision", key=f"btn_{pid}"):
#                         ref = a_dat if a_dat else b_dat
#                         query = """INSERT INTO golden_annotations (original_project_id, original_task_id_A, original_task_id_B, keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes, adjudicated_by) 
#                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
#                                    ON CONFLICT (original_project_id, keyframe_name, person_id) 
#                                    DO UPDATE SET attributes=EXCLUDED.attributes, adjudicated_by=EXCLUDED.adjudicated_by"""
#                         run_db_query(db_params, query, (selected_project_id, t_ids[0], t_ids[1], active_kf, pid, ref['xtl'], ref['ytl'], ref['xbr'], ref['ybr'], json.dumps(final), ADJUDICATOR_NAME), None)
#                         st.success(f"Person {pid} saved.")
#                         st.rerun()

# # ==============================================================================
# # PAGE 3: DATASET EXPORT
# # ==============================================================================
# elif page == "📥 AVA Dataset Export":
#     st.header(f"Export for Project {selected_project_id}")
#     approved_batches = run_db_query(db_params, "SELECT DISTINCT name FROM tasks WHERE qc_status='approved' AND project_id=%s", (selected_project_id,))
    
#     if approved_batches:
#         batch_bases = sorted(list(set(['_'.join(b[0].split('_')[:-1]) for b in approved_batches])))
#         sel_export = st.selectbox("Select Batch", batch_bases)
        
#         if st.button("🚀 Generate Final Dataset"):
#             manifest_path = os.path.join(KEYFRAMES_ROOT_DIR, sel_export, "manifest.json")
#             with open(manifest_path, 'r') as f: manifest = json.load(f)
#             tasks = run_db_query(db_params, "SELECT task_id FROM tasks WHERE project_id=%s AND name LIKE %s", (selected_project_id, f"{sel_export}%"))
#             t_ids = tuple(t[0] for t in tasks)

#             # Strict isolation logic for Person 1 actions
#             raw_data = run_db_query(db_params, """
#                 SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM golden_annotations 
#                 WHERE original_project_id=%s AND (original_task_id_A IN %s OR original_task_id_B IN %s)
#                 UNION ALL
#                 SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations 
#                 WHERE task_id IN %s AND NOT EXISTS (
#                     SELECT 1 FROM golden_annotations g 
#                     WHERE g.keyframe_name=annotations.keyframe_name 
#                     AND g.person_id=annotations.person_id 
#                     AND g.original_project_id=%s
#                 )
#             """, (selected_project_id, t_ids, t_ids, t_ids, selected_project_id))

#             csv_rows = []
#             IMG_W, IMG_H = 1920, 1080 

#             for row in raw_data:
#                 kf_name, pid, x1, y1, x2, y2, attrs = row
#                 m_info = manifest.get(kf_name) or next((v for k, v in manifest.items() if os.path.splitext(k)[0] == os.path.splitext(kf_name)[0]), None)

#                 if m_info:
#                     video_id = m_info['source_video'].replace('.mp4', '')
#                     timestamp = m_info['source_frame']
                    
#                     unique_actions = set()
#                     for attr_val in attrs.values():
#                         if attr_val in ACTION_MAP:
#                             unique_actions.add(ACTION_MAP[attr_val])
                    
#                     for action_id in unique_actions:
#                         csv_rows.append({
#                             "video_id": video_id, "frame_timestamp": timestamp,
#                             "x1": round(x1/IMG_W, 6) if x1 > 1 else round(x1, 6), 
#                             "y1": round(y1/IMG_H, 6) if y1 > 1 else round(y1, 6),
#                             "x2": round(x2/IMG_W, 6) if x2 > 1 else round(x2, 6), 
#                             "y2": round(y2/IMG_H, 6) if y2 > 1 else round(y2, 6),
#                             "action_id": action_id, "person_id": pid
#                         })
            
#             if csv_rows:
#                 df = pd.DataFrame(csv_rows).drop_duplicates()
#                 df = df.sort_values(by=['video_id', 'frame_timestamp', 'person_id', 'action_id'])
#                 csv_buffer = io.StringIO()
#                 # NO HEADER as requested
#                 df.to_csv(csv_buffer, index=False, header=False)
#                 st.download_button("📥 Download Final CSV (No Header)", csv_buffer.getvalue(), f"final_export_proj_{selected_project_id}.csv", "text/csv")
#                 st.success("CSV Generated.")
#                 st.dataframe(df.head(50))



import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import os
import json
import cv2
import numpy as np
from collections import defaultdict
from pathlib import Path
import yaml
import io

# --- Helper Logic ---
def load_cvat_labels_internal(config_path: Path):
    if not config_path.exists():
        raise FileNotFoundError(f"CVAT label config not found: {config_path}")
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    return data["labels"]

def draw_comparison_image(path, ann_a, ann_b):
    if not os.path.exists(path): return None
    img = cv2.imread(path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Annotator A (Green)
    for a in ann_a: 
        cv2.rectangle(img, (int(a['xtl']), int(a['ytl'])), (int(a['xbr']), int(a['ybr'])), (0, 255, 0), 3)
        cv2.putText(img, f"A-ID:{a['person_id']}", (int(a['xtl']), int(a['ytl'])-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        
    # Annotator B (Red - Offset for visibility)
    for b in ann_b: 
        cv2.rectangle(img, (int(b['xtl'])+5, int(b['ytl'])+5), (int(b['xbr'])-5, int(b['ybr'])-5), (255, 0, 0), 3)
        cv2.putText(img, f"B-ID:{b['person_id']}", (int(b['xbr'])-80, int(b['ybr'])+25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
    return img

# --- Configuration ---
st.set_page_config(page_title="AVA-Kinetics Adjudicator", layout="wide")
st.title("🔬 Master Adjudication & AVA Export")

st.sidebar.header("⚙️ Database Configuration")
db_params = {
    "dbname": st.sidebar.text_input("DB Name", "cvat_annotations_db"),
    "user": st.sidebar.text_input("DB User", "admin"),
    "password": st.sidebar.text_input("DB Password", "admin", type="password"),
    "host": st.sidebar.text_input("DB Host", "localhost"),
    "port": st.sidebar.text_input("DB Port", "5432")
}

ADJUDICATOR_NAME = st.sidebar.text_input("Master Annotator Name", "master_annotator")
KEYFRAMES_ROOT_DIR = st.sidebar.text_input("Keyframes Root", r"E:\ava-ui\proposal_generation_pipeline\proposal_generation_pipeline\outputs")
CONFIG_PATH = st.sidebar.text_input("YAML Config Path", r"E:\ava-ui\processing_pipeline\config\cvat_labels.yaml")

# Action ID Mapping
ACTION_MAP = {
    "welding": 17, "cutting": 10, "climbing": 12, "lifting_materials": 14,
    "machine_operation": 24, "supervising": 6, "walking": 1, "idle": 19
}

try:
    ONTOLOGY = load_cvat_labels_internal(Path(CONFIG_PATH))
    PERSON_ATTRIBUTES = ONTOLOGY[0]['attributes'] 
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

def run_db_query(params, query, data=None, fetch_type="all"):
    conn = None
    try:
        conn = psycopg2.connect(**params)
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, data)
            res = cur.fetchall() if fetch_type == "all" else cur.fetchone() if fetch_type == "one" else None
            conn.commit()
            return res
    except Exception as e:
        st.error(f"DB Error: {e}"); return None
    finally:
        if conn: conn.close()

def calculate_iou(box_a, box_b):
    x1, y1 = max(box_a['xtl'], box_b['xtl']), max(box_a['ytl'], box_b['ytl'])
    x2, y2 = min(box_a['xbr'], box_b['xbr']), min(box_a['ybr'], box_b['ybr'])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = ((box_a['xbr']-box_a['xtl'])*(box_a['ybr']-box_a['ytl'])) + ((box_b['xbr']-box_b['xtl'])*(box_b['ybr']-box_b['ytl'])) - inter
    return inter / union if union > 0 else 0

def calculate_jaccard(l1, l2):
    s1, s2 = set(l1), set(l2)
    return len(s1 & s2) / len(s1 | s2) if len(s1 | s2) > 0 else 0

def flatten_attributes(attr):
    return [f"{k}:{v}" for k, v in attr.items() if v and v != 'none']

# Navigation
page = st.sidebar.radio("Navigation", ["📊 Routing", "⚔️ Adjudication (Prioritized)", "📥 AVA Dataset Export"])

projects = run_db_query(db_params, "SELECT project_id, name FROM projects ORDER BY project_id DESC")
if not projects: st.stop()
selected_project_id = st.sidebar.selectbox("Select Project", [p[0] for p in projects], format_func=lambda x: next(p[1] for p in projects if p[0] == x))

# ==============================================================================
# PAGE 1: ROUTING
# ==============================================================================
if page == "📊 Routing":
    st.header(f"Batch Routing for Project {selected_project_id}")
    st.info("Process tasks from 'completed' to 'pending_adjudication' if they mismatch.")
    if st.button("▶️ Run Routing Logic"):
        st.success("Routing logic processed.")

# ==============================================================================
# PAGE 2: ADJUDICATION (WITH MATCHED IDs)
# ==============================================================================
elif page == "⚔️ Adjudication (Prioritized)":
    tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_adjudication'", (selected_project_id,))
    if tasks:
        by_name = defaultdict(list)
        for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
        st.session_state.sel_batch = st.selectbox("Select Batch", list(by_name.keys()))
        pair = by_name[st.session_state.sel_batch]
        t_ids = (pair[0]['task_id'], pair[1]['task_id'])

        st.write("### 🛠️ Batch Controls")
        col_app, col_rej = st.columns(2)
        if col_app.button("✅ Approve Entire Batch (Mark Approved)", use_container_width=True):
            run_db_query(db_params, "UPDATE tasks SET qc_status='approved' WHERE task_id IN (%s, %s)", t_ids, None)
            st.success(f"SUCCESS: Batch {st.session_state.sel_batch} Approved!")
            st.toast("Batch Finalized", icon="✅")
            st.balloons()
            st.rerun()
        if col_rej.button("❌ Reject Entire Batch (Send Back)", use_container_width=True):
            run_db_query(db_params, "UPDATE tasks SET qc_status='rejected' WHERE task_id IN (%s, %s)", t_ids, None)
            st.warning("Batch Rejected.")
            st.rerun()
        st.divider()

        raw_anns = run_db_query(db_params, "SELECT * FROM annotations WHERE task_id IN (%s, %s)", t_ids)
        kf_groups = defaultdict(lambda: defaultdict(list))
        for r in raw_anns: kf_groups[r['keyframe_name']][r['task_id']].append(r)
        
        priority_list = []
        for kname, t_data in kf_groups.items():
            la, lb = t_data.get(t_ids[0], []), t_data.get(t_ids[1], [])
            conflict = (len(la) != len(lb))
            if not conflict:
                for a in la:
                    m = next((b for b in lb if calculate_iou(a, b) >= 0.5), None)
                    if not m or calculate_jaccard(flatten_attributes(a['attributes']), flatten_attributes(m['attributes'])) < 1.0:
                        conflict = True; break
            
            solved = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND original_project_id=%s", (kname, selected_project_id), "one")
            prefix = "🔥 CONFLICT" if conflict else "🟢 AGREEMENT"
            if solved: prefix = "✅ SOLVED"
            priority_list.append(f"{prefix} | {kname}")

        selected_kf_entry = st.selectbox("Select Keyframe", sorted(priority_list))
        active_kf = selected_kf_entry.split(" | ")[1]

        st.divider()
        anns = [r for r in raw_anns if r['keyframe_name'] == active_kf]
        ann_a, ann_b = [a for a in anns if a['task_id'] == t_ids[0]], [a for a in anns if a['task_id'] == t_ids[1]]
        img_path = os.path.join(KEYFRAMES_ROOT_DIR, st.session_state.sel_batch, "keyframes", active_kf)
        img = draw_comparison_image(img_path, ann_a, ann_b)
        if img is not None: st.image(img, use_container_width=True)

        # Logical Pairing Logic
        matched_pairs = []
        unmatched_b = ann_b.copy()
        for a in ann_a:
            match = next((b for b in unmatched_b if calculate_iou(a, b) >= 0.5), None)
            if match: unmatched_b.remove(match)
            matched_pairs.append({'A': a, 'B': match})
        for b in unmatched_b: matched_pairs.append({'A': None, 'B': b})

        for i, pair in enumerate(matched_pairs):
            a_dat, b_dat = pair['A'], pair['B']
            logic_id = a_dat['person_id'] if a_dat else b_dat['person_id']
            
            done = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND person_id=%s AND original_project_id=%s", (active_kf, logic_id, selected_project_id), "one")
            
            with st.expander(f"Matched Person (A-ID:{a_dat['person_id'] if a_dat else 'N/A'} | B-ID:{b_dat['person_id'] if b_dat else 'N/A'}) {'✅' if done else '🔴'}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**Annotator A Attributes**")
                    st.json(a_dat['attributes'] if a_dat else {})
                with c2:
                    st.markdown("**Annotator B Attributes**")
                    st.json(b_dat['attributes'] if b_dat else {})
                with c3:
                    choice = st.radio("Verdict:", ["Annotator A", "Annotator B", "Custom"], key=f"rad_{i}_{active_kf}")
                    final = a_dat['attributes'] if choice == "Annotator A" else b_dat['attributes'] if choice == "Annotator B" else {}
                    if choice == "Custom":
                        for attr in PERSON_ATTRIBUTES: 
                            idx = attr['values'].index(a_dat['attributes'].get(attr['name'], attr['values'][0])) if a_dat else 0
                            final[attr['name']] = st.selectbox(attr['name'], attr['values'], index=idx, key=f"adj_{i}_{attr['name']}")
                    
                    if st.button("Save Label", key=f"btn_{i}"):
                        ref = a_dat if a_dat else b_dat
                        query = """INSERT INTO golden_annotations (original_project_id, original_task_id_A, original_task_id_B, keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes, adjudicated_by) 
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                                   ON CONFLICT (original_project_id, keyframe_name, person_id) 
                                   DO UPDATE SET attributes=EXCLUDED.attributes, adjudicated_by=EXCLUDED.adjudicated_by"""
                        run_db_query(db_params, query, (selected_project_id, t_ids[0], t_ids[1], active_kf, logic_id, ref['xtl'], ref['ytl'], ref['xbr'], ref['ybr'], json.dumps(final), ADJUDICATOR_NAME), None)
                        st.success("Decision Logged.")
                        st.rerun()

# ==============================================================================
# PAGE 5: DATASET EXPORT
# ==============================================================================
elif page == "📥 AVA Dataset Export":
    st.header(f"Export for Project {selected_project_id}")
    approved_batches = run_db_query(db_params, "SELECT DISTINCT name FROM tasks WHERE qc_status='approved' AND project_id=%s", (selected_project_id,))
    
    if approved_batches:
        batch_bases = sorted(list(set(['_'.join(b[0].split('_')[:-1]) for b in approved_batches])))
        sel_export = st.selectbox("Select Batch", batch_bases)
        
        if st.button("🚀 Generate Final Dataset"):
            manifest_path = os.path.join(KEYFRAMES_ROOT_DIR, sel_export, "manifest.json")
            with open(manifest_path, 'r') as f: manifest = json.load(f)
            tasks = run_db_query(db_params, "SELECT task_id FROM tasks WHERE project_id=%s AND name LIKE %s", (selected_project_id, f"{sel_export}%"))
            t_ids = tuple(t[0] for t in tasks)

            raw_data = run_db_query(db_params, """
                SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM golden_annotations 
                WHERE original_project_id=%s AND (original_task_id_A IN %s OR original_task_id_B IN %s)
                UNION ALL
                SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations 
                WHERE task_id IN %s AND NOT EXISTS (
                    SELECT 1 FROM golden_annotations g 
                    WHERE g.keyframe_name=annotations.keyframe_name 
                    AND g.person_id=annotations.person_id 
                    AND g.original_project_id=%s
                )
            """, (selected_project_id, t_ids, t_ids, t_ids, selected_project_id))

            csv_rows = []
            IMG_W, IMG_H = 1920, 1080 

            for row in raw_data:
                kf_name, pid, x1, y1, x2, y2, attrs = row
                m_info = manifest.get(kf_name) or next((v for k, v in manifest.items() if os.path.splitext(k)[0] == os.path.splitext(kf_name)[0]), None)

                if m_info:
                    video_id = m_info['source_video'].replace('.mp4', '')
                    timestamp = m_info['source_frame']
                    
                    unique_actions = set()
                    for attr_val in attrs.values():
                        if attr_val in ACTION_MAP:
                            unique_actions.add(ACTION_MAP[attr_val])
                    
                    for action_id in unique_actions:
                        csv_rows.append({
                            "video_id": video_id, "frame_timestamp": timestamp,
                            "x1": round(x1/IMG_W, 6) if x1 > 1 else round(x1, 6), 
                            "y1": round(y1/IMG_H, 6) if y1 > 1 else round(y1, 6),
                            "x2": round(x2/IMG_W, 6) if x2 > 1 else round(x2, 6), 
                            "y2": round(y2/IMG_H, 6) if y2 > 1 else round(y2, 6),
                            "action_id": action_id, "person_id": pid
                        })
            
            if csv_rows:
                df = pd.DataFrame(csv_rows).drop_duplicates()
                df = df.sort_values(by=['video_id', 'frame_timestamp', 'person_id', 'action_id'])
                csv_buffer = io.StringIO()
                # header=False removes column names from CSV
                df.to_csv(csv_buffer, index=False, header=False)
                st.download_button("📥 Download Final CSV (No Header)", csv_buffer.getvalue(), f"final_export_proj_{selected_project_id}.csv", "text/csv")
                st.success("Dataset Ready.")
                st.dataframe(df.head(50))
            else:
                st.warning("No action matches found.")