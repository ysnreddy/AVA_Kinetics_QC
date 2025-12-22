# import streamlit as st
# import psycopg2
# import psycopg2.extras
# import pandas as pd
# import os
# import json
# import cv2
# import numpy as np
# from collections import defaultdict
# import random
# from pathlib import Path
# import yaml
# from typing import List, Dict, Any

# # --- Label Loader Logic ---
# def load_cvat_labels_internal(config_path: Path) -> List[Dict[str, Any]]:
#     if not config_path.exists():
#         raise FileNotFoundError(f"CVAT label config not found: {config_path}")
#     with open(config_path, "r") as f:
#         data = yaml.safe_load(f)
#     if "labels" not in data:
#         raise ValueError("Invalid label config: 'labels' key missing")
#     return data["labels"]

# def draw_blind_audit_image(path, ann):
#     """Draws ONLY the box for the specific person being audited (No Labels)."""
#     if not os.path.exists(path): return None
#     img = cv2.imread(path)
#     if img is None: return None
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#     cv2.rectangle(img, (int(ann['xtl']), int(ann['ytl'])), (int(ann['xbr']), int(ann['ybr'])), (255, 255, 0), 3)
#     return img

# def draw_comparison_image(path, ann_a, ann_b):
#     if not os.path.exists(path): return None
#     img = cv2.imread(path)
#     if img is None: return None
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#     for a in ann_a: cv2.rectangle(img, (int(a['xtl']), int(a['ytl'])), (int(a['xbr']), int(a['ybr'])), (0, 255, 0), 2)
#     for b in ann_b: cv2.rectangle(img, (int(b['xtl'])+4, int(b['ytl'])+4), (int(b['xbr'])-4, int(b['ybr'])-4), (255, 0, 0), 2)
#     return img

# # --- Configuration ---
# st.set_page_config(page_title="AVA-Kinetics 2+1 Adjudication", layout="wide")
# st.title("🔬 AVA-Kinetics 2+1 Adjudication System")

# if 'sel_batch' not in st.session_state: st.session_state.sel_batch = None
# if 'sel_kf' not in st.session_state: st.session_state.sel_kf = None

# st.sidebar.header("⚙️ Database Configuration")
# db_params = {
#     "dbname": st.sidebar.text_input("DB Name", "cvat_annotations_db"),
#     "user": st.sidebar.text_input("DB User", "admin"),
#     "password": st.sidebar.text_input("DB Password", "admin", type="password"),
#     "host": st.sidebar.text_input("DB Host", "localhost"),
#     "port": st.sidebar.text_input("DB Port", "5432")
# }

# ADJUDICATOR_NAME = st.sidebar.text_input("Master Annotator Name", "master_annotator")
# KEYFRAMES_ROOT_DIR = st.sidebar.text_input("Keyframes Root Directory", r"E:\ava-ui\proposal_generation_pipeline\proposal_generation_pipeline\outputs")
# CONFIG_PATH = st.sidebar.text_input("YAML Config Path", r"E:\ava-ui\processing_pipeline\config\cvat_labels.yaml")

# # --- Load Ontology ---
# try:
#     ONTOLOGY = load_cvat_labels_internal(Path(CONFIG_PATH))
#     PERSON_ATTRIBUTES = ONTOLOGY[0]['attributes'] 
# except Exception as e:
#     st.error(f"Failed to load ontology: {e}")
#     st.stop()

# # --- Helper Functions ---
# def get_db_connection(params):
#     try: return psycopg2.connect(**params)
#     except Exception: return None

# def run_db_query(params, query, data=None, fetch_type="all"):
#     conn = get_db_connection(params)
#     if conn:
#         try:
#             with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#                 cur.execute(query, data)
#                 res = cur.fetchall() if fetch_type == "all" else cur.fetchone() if fetch_type == "one" else None
#                 conn.commit()
#             return res
#         except Exception as e:
#             st.error(f"Database Error: {e}")
#             return None
#         finally:
#             conn.close()
#     return None

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

# # --- Protocol Functions ---
# def check_agreement(t1, t2, params):
#     anns = run_db_query(params, "SELECT * FROM annotations WHERE task_id IN (%s, %s)", (t1, t2))
#     kfs = defaultdict(lambda: defaultdict(list))
#     for a in anns: kfs[a['keyframe_name']][a['task_id']].append(a)
#     for kf, tasks in kfs.items():
#         la, lb = tasks.get(t1, []), tasks.get(t2, [])
#         if len(la) != len(lb): return False
#         for a in la:
#             m = next((b for b in lb if calculate_iou(a, b) >= 0.5), None)
#             if not m or calculate_jaccard(flatten_attributes(a['attributes']), flatten_attributes(m['attributes'])) < 1.0: return False
#     return True

# def apply_stratified_sampling(task_pairs):
#     strata = defaultdict(list)
#     for p in task_pairs: strata[p['task_a']['assignee']].append(p)
#     audit, auto = [], []
#     for assignee, pairs in strata.items():
#         random.shuffle(pairs)
#         n = int(len(pairs) * 0.6)
#         if n == 0 and len(pairs) > 0: n = 1
#         audit.extend(pairs[:n]); auto.extend(pairs[n:])
#     return audit, auto

# # --- Sidebar Logic ---
# projects = run_db_query(db_params, "SELECT project_id, name FROM projects ORDER BY project_id DESC")
# if not projects: st.stop()
# selected_project_id = st.sidebar.selectbox("Select Project", [p[0] for p in projects], format_func=lambda x: next(p[1] for p in projects if p[0] == x))
# page = st.sidebar.radio("Navigation", ["📊 Dashboard & Routing", "⚔️ Adjudication Queue", "🔍 Blind Audit Queue","📈 Batch Quality Report"])

# # ==============================================================================
# # PAGE 1: DASHBOARD & ROUTING
# # ==============================================================================
# if page == "📊 Dashboard & Routing":
#     st.header("Protocol 1 & 2: Routing & Sampling")
#     tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='completed'", (selected_project_id,))
#     pairs = []
#     by_name = defaultdict(list)
#     if tasks:
#         for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
#         for base, t_list in by_name.items():
#             if len(t_list) == 2: pairs.append({'batch': base, 'task_a': t_list[0], 'task_b': t_list[1]})

#     if st.button("▶️ Run Routing Logic"):
#         agreed_pairs = []
#         for p in pairs:
#             if check_agreement(p['task_a']['task_id'], p['task_b']['task_id'], db_params):
#                 agreed_pairs.append(p)
#             else:
#                 run_db_query(db_params, "UPDATE tasks SET qc_status='pending_adjudication' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
        
#         audit, auto = apply_stratified_sampling(agreed_pairs)
#         for p in audit: run_db_query(db_params, "UPDATE tasks SET qc_status='pending_audit' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
#         for p in auto: run_db_query(db_params, "UPDATE tasks SET qc_status='auto_approved' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
#         st.success(f"Processing Complete for Project {selected_project_id}. {len(audit)} to Audit.")


# # ==============================================================================
# # PAGE 2: ADJUDICATION (WITH BATCH ACTIONS)
# # ==============================================================================
# elif page == "⚔️ Adjudication Queue":
#     st.header("⚔️ Adjudication Queue")
#     tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_adjudication'", (selected_project_id,))
    
#     if tasks:
#         by_name = defaultdict(list)
#         for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
#         batch_list = list(by_name.keys())
#         st.session_state.sel_batch = st.selectbox("Select Batch", batch_list, index=batch_list.index(st.session_state.sel_batch) if st.session_state.sel_batch in batch_list else 0)
        
#         pair = by_name[st.session_state.sel_batch]
#         t_ids = (pair[0]['task_id'], pair[1]['task_id'])

#         st.divider()
#         col_stat, col_app, col_rej = st.columns([2, 1, 1])
        
#         total_anns = run_db_query(db_params, "SELECT COUNT(DISTINCT(keyframe_name, person_id)) FROM annotations WHERE task_id IN (%s, %s)", t_ids, "one")[0]
#         done_anns = run_db_query(db_params, "SELECT COUNT(*) FROM golden_annotations WHERE original_project_id=%s AND (original_task_id_A=%s OR original_task_id_B=%s)", (selected_project_id, t_ids[0], t_ids[1]), "one")[0]
        
#         col_stat.metric("Batch Adjudication Progress", f"{done_anns} / {total_anns} Instances")

#         if col_app.button("✅ Approve & Send to Blind Audit", use_container_width=True, help="Mark adjudicated batch as ready for Audit"):
#             if done_anns < total_anns:
#                 st.warning("Warning: You are approving a batch before all instances were adjudicated.")
            
#             # Directly routing adjudicated batches to 'pending_audit' to bypass stratified sampling logic [cite: 128, 168]
#             run_db_query(db_params, "UPDATE tasks SET qc_status='pending_audit' WHERE task_id IN (%s, %s)", t_ids, None)
#             st.success(f"Batch {st.session_state.sel_batch} routed to Blind Audit Queue.")
#             st.rerun()

#         if col_rej.button("❌ Reject Batch to Annotators", use_container_width=True, help="Send back to labeling"):
#             run_db_query(db_params, "UPDATE tasks SET qc_status='pending' WHERE task_id IN (%s, %s)", t_ids, None)
#             st.error(f"Batch {st.session_state.sel_batch} Rejected.")
#             st.rerun()
#         st.divider()

#         keyframes = run_db_query(db_params, """
#             SELECT DISTINCT keyframe_name, 
#             EXISTS(SELECT 1 FROM golden_annotations WHERE keyframe_name=annotations.keyframe_name AND original_project_id=%s) as solved 
#             FROM annotations WHERE task_id IN (%s, %s)
#         """, (selected_project_id, t_ids[0], t_ids[1]))
        
#         kf_list = [k[0] for k in keyframes]
#         st.session_state.sel_kf = st.selectbox("Select Keyframe", kf_list, index=kf_list.index(st.session_state.sel_kf) if st.session_state.sel_kf in kf_list else 0,
#                                                format_func=lambda x: f"{x} {'✅' if next(k[1] for k in keyframes if k[0]==x) else '⚠️'}")
        
#         anns = run_db_query(db_params, "SELECT * FROM annotations WHERE task_id IN (%s, %s) AND keyframe_name=%s", (t_ids[0], t_ids[1], st.session_state.sel_kf))
#         ann_a, ann_b = [a for a in anns if a['task_id'] == t_ids[0]], [a for a in anns if a['task_id'] == t_ids[1]]
        
#         img = draw_comparison_image(os.path.join(KEYFRAMES_ROOT_DIR, st.session_state.sel_batch, "keyframes", st.session_state.sel_kf), ann_a, ann_b)
#         if img is not None: st.image(img, use_container_width=True)
        
#         for pid in sorted(set([a['person_id'] for a in anns])):
#             done = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND person_id=%s AND original_project_id=%s", (st.session_state.sel_kf, pid, selected_project_id), "one")
            
#             with st.expander(f"Person {pid} {'✅' if done else '🔴'}", expanded=not done):
#                 a_dat, b_dat = next((x for x in ann_a if x['person_id'] == pid), None), next((x for x in ann_b if x['person_id'] == pid), None)
#                 c1, c2, c3 = st.columns(3)
#                 c1.json(a_dat['attributes'] if a_dat else {}); c2.json(b_dat['attributes'] if b_dat else {})
                
#                 with c3:
#                     choice = st.radio("Verdict:", ["Annotator A", "Annotator B", "Custom"], key=f"rad_{pid}_{st.session_state.sel_kf}")
#                     final = a_dat['attributes'] if choice == "Annotator A" else b_dat['attributes'] if choice == "Annotator B" else {}
#                     if choice == "Custom":
#                         for attr in PERSON_ATTRIBUTES: final[attr['name']] = st.selectbox(attr['name'], attr['values'], key=f"adj_{pid}_{attr['name']}")
                    
#                     if st.button("Save Label", key=f"btn_{pid}"):
#                         ref = a_dat if a_dat else b_dat
#                         query = """
#                             INSERT INTO golden_annotations (
#                                 original_project_id, original_task_id_A, original_task_id_B, 
#                                 keyframe_name, person_id, xtl, ytl, xbr, ybr, 
#                                 attributes, adjudicated_by
#                             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
#                             ON CONFLICT (original_project_id, keyframe_name, person_id) 
#                             DO UPDATE SET attributes=EXCLUDED.attributes, adjudicated_by=EXCLUDED.adjudicated_by
#                         """
#                         run_db_query(db_params, query, (
#                             selected_project_id, t_ids[0], t_ids[1], 
#                             st.session_state.sel_kf, pid, ref['xtl'], ref['ytl'], 
#                             ref['xbr'], ref['ybr'], json.dumps(final), ADJUDICATOR_NAME
#                         ), None)
#                         st.rerun()
#     else:
#         st.success("Queue empty! No batches pending adjudication.")

# # ==============================================================================
# # PAGE 3: BLIND AUDIT (Systematic Batch Review)
# # ==============================================================================
# elif page == "🔍 Blind Audit Queue":
#     st.header("🔍 Blind Audit (Zero Tolerance)")
    
#     tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_audit'", (selected_project_id,))
    
#     if tasks:
#         by_batch = defaultdict(list)
#         for t in tasks: 
#             batch_base_name = '_'.join(t['name'].split('_')[:-1])
#             by_batch[batch_base_name].append(t)
        
#         batch_list = list(by_batch.keys())
#         sel_audit_batch = st.selectbox("Select Batch for Audit", batch_list)
        
#         batch_tasks = by_batch[sel_audit_batch]
#         t_ids = tuple(t['task_id'] for t in batch_tasks)
        
#         # Protocol: Audit 60 items per batch of 100 for <5% error bound [cite: 85, 87]
#         total_in_batch = run_db_query(db_params, "SELECT COUNT(*) FROM annotations WHERE task_id IN %s", (t_ids,), "one")[0]
#         audited_in_batch = run_db_query(db_params, "SELECT COUNT(*) FROM audits WHERE task_id IN %s", (t_ids,), "one")[0]
        
#         st.info(f"Audit Progress for {sel_audit_batch}: {audited_in_batch} / {min(60, total_in_batch)} target completed.")

#         if st.button("🚨 Emergency Reject Entire Batch", type="primary"):
#             run_db_query(db_params, "UPDATE tasks SET qc_status='rejected' WHERE task_id IN %s", (t_ids,), None)
#             st.rerun()

#         ann = run_db_query(db_params, """
#             SELECT a.* FROM annotations a 
#             WHERE a.task_id IN %s 
#             AND NOT EXISTS (SELECT 1 FROM audits WHERE task_id=a.task_id AND person_id=a.person_id) 
#             LIMIT 1
#         """, (t_ids,), "one")

#         if ann:
#             st.subheader(f"Blinded Review: Person {ann['person_id']} in {ann['keyframe_name']}")
#             img = draw_blind_audit_image(os.path.join(KEYFRAMES_ROOT_DIR, sel_audit_batch, "keyframes", ann['keyframe_name']), ann)
            
#             if img is not None: 
#                 st.image(img, use_container_width=True)
            
#             expert_attrs = {}
#             cols = st.columns(3)
#             for i, attr in enumerate(PERSON_ATTRIBUTES): 
#                 expert_attrs[attr['name']] = cols[i % 3].selectbox(f"Expert {attr['name']}", attr['values'], key=f"aud_{attr['name']}")
            
#             if st.button("Submit Audit Decision"):
#                 # Protocol 3: Zero Tolerance. Mismatch -> Reject Entire Batch [cite: 67, 69, 94]
#                 overturn = (expert_attrs != ann['attributes'])
                
#                 run_db_query(db_params, """
#                     INSERT INTO audits (task_id, keyframe_name, person_id, original_consensus_attributes, auditor_attributes, is_overturn, auditor_id) 
#                     VALUES (%s, %s, %s, %s, %s, %s, %s)
#                 """, (ann['task_id'], ann['keyframe_name'], ann['person_id'], json.dumps(ann['attributes']), json.dumps(expert_attrs), overturn, ADJUDICATOR_NAME), None)
                
#                 if overturn:
#                     run_db_query(db_params, "UPDATE tasks SET qc_status='rejected' WHERE task_id IN %s", (t_ids,), None)
#                     st.error(f"AUDIT FAIL: Batch {sel_audit_batch} REJECTED.")
#                 st.rerun()
#         else:
#             # Audit complete (0 errors) [cite: 71, 93]
#             st.success(f"Audit of {audited_in_batch} items complete with 0 errors.")
#             if st.button(f"✅ Approve Batch {sel_audit_batch}"):
#                 run_db_query(db_params, "UPDATE tasks SET qc_status='approved' WHERE task_id IN %s", (t_ids,), None)
#                 st.balloons()
#                 st.rerun()
#     else:
#         st.success("Blind Audit Queue is empty.")


# # Add "📈 Batch Quality Report" to your navigation radio buttons in the sidebar
# # page = st.sidebar.radio("Navigation", ["📊 Dashboard & Routing", "⚔️ Adjudication Queue", "🔍 Blind Audit Queue", "📈 Batch Quality Report"])

# elif page == "📈 Batch Quality Report":
#     st.header("📈 Batch Quality Index (BQI) Analysis")
    
#     # 1. Select a Batch that is either 'approved' or 'rejected'
#     completed_tasks = run_db_query(db_params, "SELECT DISTINCT name FROM tasks WHERE qc_status IN ('approved', 'rejected')")
#     if not completed_tasks:
#         st.info("No completed batches available for BQI reporting yet.")
#     else:
#         batch_bases = sorted(list(set(['_'.join(t[0].split('_')[:-1]) for t in completed_tasks])))
#         sel_bqi_batch = st.selectbox("Select Batch for Quality Report", batch_bases)
        
#         # 2. Gather Metrics from Database
#         tasks = run_db_query(db_params, "SELECT task_id FROM tasks WHERE name LIKE %s", (f"{sel_bqi_batch}%",))
#         t_ids = tuple(t[0] for t in tasks)
        
#         # Metric A: Audit Error Rate
#         audit_data = run_db_query(db_params, "SELECT COUNT(*) as total, SUM(CASE WHEN is_overturn THEN 1 ELSE 0 END) as errors FROM audits WHERE task_id IN %s", (t_ids,), "one")
#         audit_n = audit_data[0] if audit_data[0] > 0 else 1
#         audit_errors = audit_data[1] if audit_data[1] else 0
#         audit_error_rate = audit_errors / audit_n # [cite: 119]
        
#         # Metric B: Median IoU (Spatial Consistency)
#         # Note: In production, this would use a 'box_matches' table as per doc [cite: 266, 561]
#         iou_res = run_db_query(db_params, "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (xtl+ytl+xbr+ybr)/4000) FROM annotations WHERE task_id IN %s", (t_ids,), "one")
#         median_iou = iou_res[0] if iou_res[0] else 0.85 # Defaulting if no overlap data
        
#         # Metric C: Target Error (τ) from config
#         target_tau = 0.05 # [cite: 120, 168]

#         # 3. Calculate Penalties [cite: 188-193]
#         penalty_audit = 40 * min(1.0, audit_error_rate / target_tau)
#         penalty_iou = 20 * max(0.0, (0.50 - median_iou) / 0.50)
        
#         # Simplified BQI for UI (Add ME% and Kappa logic as your database grows)
#         bqi_score = 100 - penalty_audit - penalty_iou
        
#         # 4. Display Report [cite: 124-127]
#         st.subheader(f"Batch Health: {sel_bqi_batch}")
        
#         c1, c2, c3 = st.columns(3)
#         c1.metric("BQI Score", f"{bqi_score:.1f}/100")
#         c2.metric("Audit Error Rate", f"{audit_error_rate*100:.1f}%", delta=f"{target_tau*100}% Target", delta_color="inverse")
#         c3.metric("Median IoU", f"{median_iou:.2f}")

#         # Quality Band Interpretation [cite: 194]
#         if bqi_score >= 90:
#             st.success("✅ PASS: High Quality Batch")
#         elif 80 <= bqi_score < 90:
#             st.warning("⚠️ LIGHT REWORK: Targeted fixes recommended")
#         else:
#             st.error("🚨 FAIL: Re-annotate or Retrain required")
            
#         st.divider()
#         st.write("### Detailed Penalties")
#         st.table({
#             "Metric": ["Audit Errors", "Spatial Overlap (IoU)"],
#             "Value": [f"{audit_errors} fails in {audit_n} samples", f"{median_iou:.2f} median"],
#             "BQI Deduction": [f"-{penalty_audit:.1f}", f"-{penalty_iou:.1f}"]
#         })




import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import os
import json
import cv2
import numpy as np
from collections import defaultdict
import random
from pathlib import Path
import yaml
from typing import List, Dict, Any
import io

# --- Label Loader Logic ---
def load_cvat_labels_internal(config_path: Path) -> List[Dict[str, Any]]:
    if not config_path.exists():
        raise FileNotFoundError(f"CVAT label config not found: {config_path}")
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    if "labels" not in data:
        raise ValueError("Invalid label config: 'labels' key missing")
    return data["labels"]

def draw_blind_audit_image(path, ann):
    if not os.path.exists(path): return None
    img = cv2.imread(path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    cv2.rectangle(img, (int(ann['xtl']), int(ann['ytl'])), (int(ann['xbr']), int(ann['ybr'])), (255, 255, 0), 3)
    cv2.putText(img, f"ID:{ann['person_id']}", (int(ann['xtl']), int(ann['ytl'])-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,0), 2)
    return img

def draw_comparison_image(path, ann_a, ann_b):
    if not os.path.exists(path): return None
    img = cv2.imread(path)
    if img is None: return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # Annotator A (Green)
    for a in ann_a: 
        cv2.rectangle(img, (int(a['xtl']), int(a['ytl'])), (int(a['xbr']), int(a['ybr'])), (0, 255, 0), 2)
        cv2.putText(img, f"A-ID:{a['person_id']}", (int(a['xtl']), int(a['ytl'])-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
    # Annotator B (Red - Offset for visibility)
    for b in ann_b: 
        cv2.rectangle(img, (int(b['xtl'])+4, int(b['ytl'])+4), (int(b['xbr'])-4, int(b['ybr'])-4), (255, 0, 0), 2)
        cv2.putText(img, f"B-ID:{b['person_id']}", (int(b['xbr'])-60, int(b['ybr'])+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)
    return img

# --- Configuration ---
st.set_page_config(page_title="AVA-Kinetics 2+1 Adjudication", layout="wide")
st.title("🔬 AVA-Kinetics 2+1 Adjudication System")

if 'sel_batch' not in st.session_state: st.session_state.sel_batch = None
if 'sel_kf' not in st.session_state: st.session_state.sel_kf = None

st.sidebar.header("⚙️ Database Configuration")
db_params = {
    "dbname": st.sidebar.text_input("DB Name", "cvat_annotations_db"),
    "user": st.sidebar.text_input("DB User", "admin"),
    "password": st.sidebar.text_input("DB Password", "admin", type="password"),
    "host": st.sidebar.text_input("DB Host", "localhost"),
    "port": st.sidebar.text_input("DB Port", "5432")
}

ADJUDICATOR_NAME = st.sidebar.text_input("Master Annotator Name", "master_annotator")
KEYFRAMES_ROOT_DIR = st.sidebar.text_input("Keyframes Root Directory", r"E:\ava-ui\proposal_generation_pipeline\proposal_generation_pipeline\outputs")
CONFIG_PATH = st.sidebar.text_input("YAML Config Path", r"E:\ava-ui\processing_pipeline\config\cvat_labels.yaml")

try:
    ONTOLOGY = load_cvat_labels_internal(Path(CONFIG_PATH))
    PERSON_ATTRIBUTES = ONTOLOGY[0]['attributes'] 
except Exception as e:
    st.error(f"Failed to load ontology: {e}")
    st.stop()

def get_db_connection(params):
    try: return psycopg2.connect(**params)
    except Exception: return None

def run_db_query(params, query, data=None, fetch_type="all"):
    conn = get_db_connection(params)
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, data)
                res = cur.fetchall() if fetch_type == "all" else cur.fetchone() if fetch_type == "one" else None
                conn.commit()
            return res
        except Exception as e:
            st.error(f"Database Error: {e}")
            return None
        finally:
            conn.close()
    return None

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

def check_agreement(t1, t2, params):
    anns = run_db_query(params, "SELECT * FROM annotations WHERE task_id IN (%s, %s)", (t1, t2))
    kfs = defaultdict(lambda: defaultdict(list))
    for a in anns: kfs[a['keyframe_name']][a['task_id']].append(a)
    for kf, tasks in kfs.items():
        la, lb = tasks.get(t1, []), tasks.get(t2, [])
        if len(la) != len(lb): return False
        for a in la:
            m = next((b for b in lb if calculate_iou(a, b) >= 0.5), None)
            if not m or calculate_jaccard(flatten_attributes(a['attributes']), flatten_attributes(m['attributes'])) < 1.0: return False
    return True

def apply_stratified_sampling(task_pairs):
    strata = defaultdict(list)
    for p in task_pairs: strata[p['task_a']['assignee']].append(p)
    audit, auto = [], []
    for assignee, pairs in strata.items():
        random.shuffle(pairs)
        n = int(len(pairs) * 0.6)
        if n == 0 and len(pairs) > 0: n = 1
        audit.extend(pairs[:n]); auto.extend(pairs[n:])
    return audit, auto

projects = run_db_query(db_params, "SELECT project_id, name FROM projects ORDER BY project_id DESC")
if not projects: st.stop()
selected_project_id = st.sidebar.selectbox("Select Project", [p[0] for p in projects], format_func=lambda x: next(p[1] for p in projects if p[0] == x))
page = st.sidebar.radio("Navigation", ["📊 Dashboard & Routing", "⚔️ Adjudication Queue", "🔍 Blind Audit Queue", "📈 Batch Quality Report", "📥 Dataset Export"])

# ==============================================================================
# PAGE 1: ROUTING
# ==============================================================================
if page == "📊 Dashboard & Routing":
    st.header("Protocol 1 & 2: Routing & Sampling")
    tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='completed'", (selected_project_id,))
    pairs = []
    by_name = defaultdict(list)
    if tasks:
        for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
        for base, t_list in by_name.items():
            if len(t_list) == 2: pairs.append({'batch': base, 'task_a': t_list[0], 'task_b': t_list[1]})

    if st.button("▶️ Run Routing Logic"):
        agreed_pairs = []
        for p in pairs:
            if check_agreement(p['task_a']['task_id'], p['task_b']['task_id'], db_params):
                agreed_pairs.append(p)
            else:
                run_db_query(db_params, "UPDATE tasks SET qc_status='pending_adjudication' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
        
        audit, auto = apply_stratified_sampling(agreed_pairs)
        for p in audit: run_db_query(db_params, "UPDATE tasks SET qc_status='pending_audit' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
        for p in auto: run_db_query(db_params, "UPDATE tasks SET qc_status='auto_approved' WHERE task_id IN (%s, %s) AND project_id=%s", (p['task_a']['task_id'], p['task_b']['task_id'], selected_project_id), None)
        st.success(f"Routing Complete. {len(audit)} to Audit.")

# ==============================================================================
# PAGE 2: ADJUDICATION (WITH CONFLICT PRIORITIZATION)
# ==============================================================================
elif page == "⚔️ Adjudication Queue":
    st.header("⚔️ Adjudication Queue")
    tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_adjudication'", (selected_project_id,))
    if tasks:
        by_name = defaultdict(list)
        for t in tasks: by_name['_'.join(t['name'].split('_')[:-1])].append(t)
        batch_list = list(by_name.keys())
        st.session_state.sel_batch = st.selectbox("Select Batch", batch_list)
        pair = by_name[st.session_state.sel_batch]
        t_ids = (pair[0]['task_id'], pair[1]['task_id'])

        # PRIORITIZATION LOGIC
        # 1. Get all frames
        raw_anns = run_db_query(db_params, "SELECT * FROM annotations WHERE task_id IN (%s, %s)", t_ids)
        kf_groups = defaultdict(lambda: defaultdict(list))
        for r in raw_anns: kf_groups[r['keyframe_name']][r['task_id']].append(r)
        
        conflict_kfs, agreement_kfs = [], []
        for kname, t_data in kf_groups.items():
            la, lb = t_data.get(t_ids[0], []), t_data.get(t_ids[1], [])
            # Conflict if counts differ or any person lacks a matching jaccard=1 partner
            has_conflict = False
            if len(la) != len(lb): has_conflict = True
            else:
                for a in la:
                    m = next((b for b in lb if calculate_iou(a, b) >= 0.5), None)
                    if not m or calculate_jaccard(flatten_attributes(a['attributes']), flatten_attributes(m['attributes'])) < 1.0:
                        has_conflict = True; break
            
            solved = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND original_project_id=%s", (kname, selected_project_id), "one")
            label = f"{kname} {'✅' if solved else '⚠️'}"
            if has_conflict: conflict_kfs.append(label)
            else: agreement_kfs.append(label)

        # UI categorization
        st.subheader("🔥 High Priority: Conflict Frames")
        st.session_state.sel_kf_c = st.selectbox("Select Conflict Frame", conflict_kfs) if conflict_kfs else st.info("No conflicts remaining!")
        
        st.subheader("🟢 Standard Review: Agreement Frames")
        st.session_state.sel_kf_a = st.selectbox("Select Agreement Frame", agreement_kfs) if agreement_kfs else st.info("No agreement frames.")

        # Logic to determine which KF to display
        active_kf_label = st.session_state.sel_kf_c if conflict_kfs else st.session_state.sel_kf_a if agreement_kfs else None
        if active_kf_label:
            active_kf = active_kf_label.split(' ')[0]
            st.divider()
            st.write(f"### Reviewing: {active_kf}")
            
            anns = [r for r in raw_anns if r['keyframe_name'] == active_kf]
            ann_a, ann_b = [a for a in anns if a['task_id'] == t_ids[0]], [a for a in anns if a['task_id'] == t_ids[1]]
            img = draw_comparison_image(os.path.join(KEYFRAMES_ROOT_DIR, st.session_state.sel_batch, "keyframes", active_kf), ann_a, ann_b)
            if img is not None: st.image(img, use_container_width=True)

            for pid in sorted(set([a['person_id'] for a in anns])):
                done = run_db_query(db_params, "SELECT 1 FROM golden_annotations WHERE keyframe_name=%s AND person_id=%s AND original_project_id=%s", (active_kf, pid, selected_project_id), "one")
                with st.expander(f"Person {pid} {'✅' if done else '🔴'}"):
                    a_dat, b_dat = next((x for x in ann_a if x['person_id'] == pid), None), next((x for x in ann_b if x['person_id'] == pid), None)
                    c1, c2, c3 = st.columns(3)
                    c1.json(a_dat['attributes'] if a_dat else {}); c2.json(b_dat['attributes'] if b_dat else {})
                    with c3:
                        choice = st.radio("Verdict:", ["Annotator A", "Annotator B", "Custom"], key=f"rad_{pid}_{active_kf}")
                        final = a_dat['attributes'] if choice == "Annotator A" else b_dat['attributes'] if choice == "Annotator B" else {}
                        if choice == "Custom":
                            for attr in PERSON_ATTRIBUTES: final[attr['name']] = st.selectbox(attr['name'], attr['values'], key=f"adj_{pid}_{attr['name']}")
                        
                        if st.button("Save Label", key=f"btn_{pid}"):
                            ref = a_dat if a_dat else b_dat
                            # IF conflict OR IF custom, save to golden_annotations
                            is_conflict_kf = any(active_kf in c for c in conflict_kfs)
                            if is_conflict_kf or choice == "Custom":
                                query = """INSERT INTO golden_annotations (original_project_id, original_task_id_A, original_task_id_B, keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes, adjudicated_by) 
                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (original_project_id, keyframe_name, person_id) DO UPDATE SET attributes=EXCLUDED.attributes"""
                                run_db_query(db_params, query, (selected_project_id, t_ids[0], t_ids[1], active_kf, pid, ref['xtl'], ref['ytl'], ref['xbr'], ref['ybr'], json.dumps(final), ADJUDICATOR_NAME), None)
                            st.success("Decision Logged"); st.rerun()

        st.divider()
        if st.button("✅ Approve & Send to Blind Audit", use_container_width=True):
            run_db_query(db_params, "UPDATE tasks SET qc_status='pending_audit' WHERE task_id IN (%s, %s)", t_ids, None)
            st.success("Batch Routed to Audit"); st.rerun()

# ==============================================================================
# PAGE 3: BLIND AUDIT
# ==============================================================================
elif page == "🔍 Blind Audit Queue":
    st.header("🔍 Blind Audit (Zero Tolerance)")
    tasks = run_db_query(db_params, "SELECT * FROM tasks WHERE project_id=%s AND qc_status='pending_audit'", (selected_project_id,))
    if tasks:
        by_batch = defaultdict(list)
        for t in tasks: bname = '_'.join(t['name'].split('_')[:-1]); by_batch[bname].append(t)
        sel_audit_batch = st.selectbox("Select Batch for Audit", list(by_batch.keys()))
        batch_tasks = by_batch[sel_audit_batch]
        t_ids = tuple(t['task_id'] for t in batch_tasks)
        
        audited_in_batch = run_db_query(db_params, "SELECT COUNT(*) FROM audits WHERE task_id IN %s", (t_ids,), "one")[0]
        st.info(f"Audit Progress: {audited_in_batch} / 60")

        ann = run_db_query(db_params, "SELECT a.* FROM annotations a WHERE a.task_id IN %s AND NOT EXISTS (SELECT 1 FROM audits WHERE task_id=a.task_id AND person_id=a.person_id) LIMIT 1", (t_ids,), "one")
        if ann:
            st.subheader(f"Blinded ID:{ann['person_id']} in {ann['keyframe_name']}")
            img = draw_blind_audit_image(os.path.join(KEYFRAMES_ROOT_DIR, sel_audit_batch, "keyframes", ann['keyframe_name']), ann)
            if img is not None: st.image(img, use_container_width=True)
            expert_attrs = {}
            cols = st.columns(3)
            for i, attr in enumerate(PERSON_ATTRIBUTES): expert_attrs[attr['name']] = cols[i % 3].selectbox(f"Expert {attr['name']}", attr['values'], key=f"aud_{attr['name']}")
            
            if st.button("Submit Audit"):
                overturn = (expert_attrs != ann['attributes'])
                run_db_query(db_params, "INSERT INTO audits (task_id, keyframe_name, person_id, original_consensus_attributes, auditor_attributes, is_overturn, auditor_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (ann['task_id'], ann['keyframe_name'], ann['person_id'], json.dumps(ann['attributes']), json.dumps(expert_attrs), overturn, ADJUDICATOR_NAME), None)
                if overturn:
                    run_db_query(db_params, "UPDATE tasks SET qc_status='rejected' WHERE task_id IN %s", (t_ids,), None)
                    st.error("Audit Fail: Batch Rejected"); st.rerun()
                st.rerun()
        else:
            if st.button(f"✅ Final Approve Batch"):
                run_db_query(db_params, "UPDATE tasks SET qc_status='approved' WHERE task_id IN %s", (t_ids,), None)
                st.balloons(); st.rerun()

# ==============================================================================
# PAGE 4: BQI REPORT
# ==============================================================================
elif page == "📈 Batch Quality Report":
    st.header("📈 Batch Quality Index")
    completed_tasks = run_db_query(db_params, "SELECT DISTINCT name FROM tasks WHERE qc_status IN ('approved', 'rejected')")
    if completed_tasks:
        batch_bases = sorted(list(set(['_'.join(t[0].split('_')[:-1]) for t in completed_tasks])))
        sel_bqi_batch = st.selectbox("Select Batch", batch_bases)
        tasks = run_db_query(db_params, "SELECT task_id FROM tasks WHERE name LIKE %s", (f"{sel_bqi_batch}%",))
        t_ids = tuple(t[0] for t in tasks)
        audit_data = run_db_query(db_params, "SELECT COUNT(*) as total, SUM(CASE WHEN is_overturn THEN 1 ELSE 0 END) as errors FROM audits WHERE task_id IN %s", (t_ids,), "one")
        audit_n, audit_errors = audit_data[0] if audit_data[0] else 1, audit_data[1] if audit_data[1] else 0
        audit_rate = audit_errors / audit_n
        penalty_audit = 40 * min(1.0, audit_rate / 0.05)
        bqi = 100 - penalty_audit
        st.metric("BQI Score", f"{bqi:.1f}/100")
        if bqi >= 90: st.success("✅ PASS")
        else: st.error("🚨 FAIL")

# ==============================================================================
# PAGE 5: DATASET EXPORT
# ==============================================================================
elif page == "📥 Dataset Export":
    st.header("📥 Export Final Annotations")
    approved_tasks = run_db_query(db_params, "SELECT DISTINCT name FROM tasks WHERE qc_status='approved'")
    if approved_tasks:
        batch_bases = sorted(list(set(['_'.join(t[0].split('_')[:-1]) for t in approved_tasks])))
        sel_export = st.selectbox("Select Batch to Export", batch_bases)
        
        if st.button("Generate Dataset CSV"):
            # Fetch annotations for the batch
            tasks = run_db_query(db_params, "SELECT task_id FROM tasks WHERE name LIKE %s", (f"{sel_export}%",))
            t_ids = tuple(t[0] for t in tasks)
            
            # Combine Golden (Master Decisions) and Annotations (Agreed Decisions)
            # Use UNION: Prefer Golden if it exists for that person/frame
            raw_data = run_db_query(db_params, """
                SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM golden_annotations WHERE original_project_id=%s AND (original_task_id_A IN %s OR original_task_id_B IN %s)
                UNION ALL
                SELECT keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id IN %s 
                AND NOT EXISTS (SELECT 1 FROM golden_annotations g WHERE g.keyframe_name=annotations.keyframe_name AND g.person_id=annotations.person_id AND g.original_project_id=%s)
            """, (selected_project_id, t_ids, t_ids, t_ids, selected_project_id))
            
            if raw_data:
                df = pd.DataFrame(raw_data, columns=['keyframe', 'person_id', 'xtl', 'ytl', 'xbr', 'ybr', 'attributes'])
                # Flatten JSON attributes into columns
                attr_df = pd.json_normalize(df['attributes'])
                final_df = pd.concat([df.drop('attributes', axis=1), attr_df], axis=1)
                
                csv = final_df.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Download CSV", data=csv, file_name=f"{sel_export}_dataset.csv", mime='text/csv')
            else: st.warning("No data found for this batch.")