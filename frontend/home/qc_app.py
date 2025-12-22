import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np
import json
from collections import defaultdict
from io import BytesIO
import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
    
from processing_pipeline.services.label_loader import load_cvat_labels
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_dynamic_attributes():
    """Converts YAML labels into the ATTRIBUTE_DEFINITIONS format for the UI"""
    labels = load_cvat_labels()
    person_label = next((l for l in labels if l["name"] == "person"), None)
    if not person_label:
        st.error("Critical Error: 'person' label not found in config/cvat_labels.yaml")
        st.stop()
        
    return {
        attr["name"]: {
            "options": attr["values"],
            "default": attr.get("default_value", attr["values"][0])
        }
        for attr in person_label["attributes"]
    }

# Load the definitions once
ATTRIBUTE_DEFINITIONS = get_dynamic_attributes()
ATTRIBUTE_NAMES = list(ATTRIBUTE_DEFINITIONS.keys())



def render_qc_dashboard():
    """Main function to render the QC Dashboard"""
    
    BACKEND_URL =  os.getenv("BACKEND_URL", "http://localhost:8000/api/v1/qc")
    
    

    st.set_page_config(page_title="AVA-Kinetics QC Dashboard", layout="wide")
    st.title("🔬 AVA-Kinetics QC Dashboard")

    
    
    
    def api_call(endpoint, method="POST", data=None):
        """Make API call to backend"""
        try:
            url = f"{BACKEND_URL}/{endpoint}"
            if method == "POST":
                response = requests.post(url, json=data)
            elif method == "GET":
                response = requests.get(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"API Error: {e}")
            return None

    def get_image_from_url(url):
        """Download image from presigned URL and convert to numpy array"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            img_array = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img
        except Exception as e:
            st.error(f"Error loading image: {e}")
            return None

    def draw_comparison_image(img, annotations_a, annotations_b, assignee_a, assignee_b):
        """Draw boxes from two annotators for comparison"""
        if img is None:
            return None
        
        
        for ann in annotations_a:
            x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"ID:{ann['person_id']} ({assignee_a})", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        
        for ann in annotations_b:
            x1, y1, x2, y2 = int(ann['xtl']), int(ann['ytl']), int(ann['xbr']), int(ann['ybr'])
            cv2.rectangle(img, (x1 + 3, y1 + 3), (x2 - 3, y2 - 3), (255, 0, 0), 2)
            cv2.putText(img, f"ID:{ann['person_id']} ({assignee_b})", (x1, y2 + 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        return img

    def draw_box_on_image(img, box, color=(0, 255, 0), label=None):
        """Draw a single box for audit"""
        if img is None:
            return None
        
        x1, y1, x2, y2 = int(box['xtl']), int(box['ytl']), int(box['xbr']), int(box['ybr'])
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
        if label:
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return img


    
    st.sidebar.header("⚙️ Database Configuration")
    db_config = {
        "dbname": st.sidebar.text_input(
            "DB Name", 
            value=os.getenv("DB_NAME", "cvat_annotations_db")
        ),
        "user": st.sidebar.text_input(
            "DB User", 
            value=os.getenv("DB_USER", "admin")
        ),
        "password": st.sidebar.text_input(
            "DB Password", 
            value=os.getenv("DB_PASSWORD", "admin"), 
            type="password"
        ),
        "host": st.sidebar.text_input(
            "DB Host", 
            value=os.getenv("DB_HOST", "localhost")
        ),
        "port": st.sidebar.text_input(
            "DB Port", 
            value=int(os.getenv("DB_PORT", 55432))
        )
    }
    ADJUDICATOR_NAME = st.sidebar.text_input("Your Name (Master)", "master_annotator")

    
    st.sidebar.divider()
    st.sidebar.header("🗂️ Project Selection")

   
    projects = api_call("projects", method="POST", data=db_config)
    selected_project_id = None

    if projects:
        proj_options = {p['project_id']: f"ID {p['project_id']}: {p['name']}" for p in projects}
        selected_project_id = st.sidebar.selectbox(
            "Select Project to QC",
            options=list(proj_options.keys()),
            format_func=lambda x: proj_options[x]
        )
        st.sidebar.success(f"Active Project: {selected_project_id}")
    else:
        st.sidebar.warning("No projects found or connection failed.")
        st.stop() 

    
    page = st.sidebar.radio(
        "Navigation",
        [
            "Adjudication Queue (Conflicts)",
            "Blind Audit Queue (Random Check)",
            "Annotator Calibration (Metrics)",
            "Bulk Approval",
            "Dataset Generation"
        ]
    )

    if not selected_project_id:
        st.warning("Please select a project from the sidebar.")
        st.stop()

    if page == "Adjudication Queue (Conflicts)":
        st.header(f"⚔️ Adjudication Queue (Project {selected_project_id})")
        
        request_data = {**db_config, "project_id": selected_project_id}
        overlap_pairs = api_call("adjudication/pairs", data=request_data)
        
        if not overlap_pairs:
            st.success("No overlap tasks are currently pending review for this project.")
        else:
            df = pd.DataFrame(overlap_pairs)
            st.dataframe(df[['clip_name', 'assignee_A', 'assignee_B', 'status']], use_container_width=True)
            
            pair_idx = st.selectbox(
                "Select Pair:",
                df.index,
                format_func=lambda x: f"{df.iloc[x]['clip_name']} ({df.iloc[x]['name_A']} vs {df.iloc[x]['name_B']})"
            )
            
            if pair_idx is not None:
                pair = df.iloc[pair_idx]
                task_id_a = int(pair['task_id_A'])
                task_id_b = int(pair['task_id_B'])

                keyframe_request = {
                    **db_config,
                    "project_id": selected_project_id,
                    "task_id_a": task_id_a,
                    "task_id_b": task_id_b,
                    "keyframe_name": ""
                }
                common_keyframes = api_call("adjudication/common-keyframes", data=keyframe_request)
                
                if not common_keyframes:
                    st.warning("These tasks have no keyframes in common.")
                    st.stop()
                
                keyframe = st.selectbox("Select Keyframe:", common_keyframes)
                
                if keyframe:
                    ann_request = {**keyframe_request, "keyframe_name": keyframe}
                    annotations = api_call("adjudication/annotations", data=ann_request)

                    batch_name = pair['clip_name']
                    url_request = {
                        **db_config,
                        "project_id": selected_project_id,
                        "batch_name": batch_name,
                        "keyframe_name": keyframe
                    }
                    url_response = api_call("keyframe-url", data=url_request)
                    
                    if url_response and 'url' in url_response:
                        img = get_image_from_url(url_response['url'])
                        
                        ann_a = [a for a in annotations if a['task_id'] == task_id_a]
                        ann_b = [a for a in annotations if a['task_id'] == task_id_b]
                        
                        img = draw_comparison_image(img, ann_a, ann_b, pair['assignee_A'], pair['assignee_B']) 
                        
                        if img is not None:
                            st.image(img, caption="Comparison (A: Green, B: Red)", use_container_width=True)
                        else:
                            st.error("Failed to load image")
                    else:
                        st.error(f"Could not get image URL for {keyframe}")

                    st.subheader("Resolve Conflict")
                    all_person_ids = sorted(list(set([a['person_id'] for a in annotations])))
                    
                    for pid in all_person_ids:
                        with st.expander(f"Person {pid}", expanded=True):
                            col1, col2, col3 = st.columns(3)
                            
                            ann_from_a = next((a for a in ann_a if a['person_id'] == pid), {})
                            ann_from_b = next((a for a in ann_b if a['person_id'] == pid), {})
                            
                            with col1:
                                st.info(f"Annotator A: {pair['assignee_A']}")
                                
                                st.json(ann_from_a.get('attributes', {}))
                            
                            with col2:
                                st.info(f"Annotator B: {pair['assignee_B']}")
                                st.json(ann_from_b.get('attributes', {}))
                            
                            with col3:
                                st.markdown("**Golden Annotation**")
                                template = ann_from_a if ann_from_a else ann_from_b
                                
                                if template:
                                    with st.form(f"adj_{keyframe}_{pid}"):
                                        final_attrs = {}
                                        for k, v in ATTRIBUTE_DEFINITIONS.items():
                                            curr = template['attributes'].get(k, v.get('default', ''))
                                            try:
                                                idx = v['options'].index(curr)
                                            except ValueError:
                                                idx = 0
                                            final_attrs[k] = st.selectbox(k, v['options'], index=idx, key=f"{keyframe}_{pid}_{k}")
                                        
                                        if st.form_submit_button("Save Golden"):
                                            save_request = {
                                                **db_config,
                                                "project_id": selected_project_id,
                                                "task_id_a": task_id_a,
                                                "task_id_b": task_id_b,
                                                "keyframe_name": keyframe,
                                                "person_id": int(pid),
                                                "xtl": template['xtl'],
                                                "ytl": template['ytl'],
                                                "xbr": template['xbr'],
                                                "ybr": template['ybr'],
                                                "attributes": final_attrs,
                                                "adjudicator": ADJUDICATOR_NAME
                                            }
                                            result = api_call("adjudication/save-golden", data=save_request)
                                            if result:
                                                st.success("Golden annotation saved!")
                                    
                    st.divider()
                    if st.button("✅ Mark Batch Complete"):
                        complete_request = {
                            **db_config,
                            "project_id": selected_project_id,
                            "task_id_a": task_id_a,
                            "task_id_b": task_id_b
                        }
                        result = api_call("adjudication/mark-complete", data=complete_request)
                        if result:
                            st.success(f"Batch {pair['clip_name']} marked as complete!")
                            st.rerun()


    elif page == "Blind Audit Queue (Random Check)":
        st.header(f"🕵️‍♀️ Blind Audit Queue (Project {selected_project_id})")
        st.info("We audit 60% of agreed clips. Zero tolerance for errors (<5% with 95% confidence).")
        
        request_data = {**db_config, "project_id": selected_project_id}
        tasks = api_call("audit/pending", data=request_data)
        
        if not tasks:
            st.success("No audits pending for this project.")
        else:
            current_batch_name = '_'.join(tasks[0]['name'].split('_')[:-1]) if '_' in tasks[0]['name'] else tasks[0]['name']
            st.subheader(f"Auditing Batch: {current_batch_name}")

            stats = api_call("audit/stats", data=request_data)
            batch_stats = [s for s in stats if current_batch_name in s['name']]
            
            if batch_stats:
                total = len(batch_stats)
                errors = sum(1 for s in batch_stats if s['is_overturn'])
                accuracy = ((total - errors) / total) * 100
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Audited So Far", total)
                col2.metric("Errors Found", errors)
                col3.metric("Accuracy", f"{accuracy:.1f}%") 
                
                if errors > 0:
                    st.error(f"❌ **ZERO TOLERANCE FAILURE**: Found {errors} error(s). Batch rejected.")
            

            audit_items = api_call("audit/items", data=request_data)
            batch_audits = [a for a in audit_items if current_batch_name in a.get('task_name', '')]
            
            if not batch_audits:
                st.success(f"Audit for batch {current_batch_name} complete!")
                
                if batch_stats:
                    errors = sum(1 for s in batch_stats if s['is_overturn'])
                    if errors == 0:
                        if st.button("✅ Finalize Approval"):
                            result = api_call("audit/finalize", data=request_data)
                            if result:
                                st.balloons()
                                st.rerun()
                    else:
                        if st.button("❌ Reject Batch"):
                            result = api_call("audit/reject", data=request_data)
                            if result:
                                st.rerun()
            else:
                item = batch_audits[0]
                url_request = {
                    **db_config,
                    "project_id": selected_project_id,
                    "batch_name": current_batch_name,
                    "keyframe_name": item['keyframe_name']
                }
                url_response = api_call("keyframe-url", data=url_request)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    if url_response and 'url' in url_response:
                        img = get_image_from_url(url_response['url'])
                        box = {
                            'xtl': item.get('xtl', 0),
                            'ytl': item.get('ytl', 0),
                            'xbr': item.get('xbr', 0),
                            'ybr': item.get('ybr', 0)
                        }
                        img = draw_box_on_image(img, box, color=(255, 255, 0), label=f"Person {item['person_id']}") 
                        
                        if img is not None:
                            st.image(img, caption="Annotation for Audit (Yellow Box)", use_container_width=True)
                        else:
                            st.error("Failed to load image")
                    else:
                        st.error(f"Could not get image URL for {item['keyframe_name']}")
                
                with col2:
                    st.markdown(f"### Audit Person {item['person_id']}")
                    with st.form("audit_form"):
                        audit_attrs = {}
                        original = item.get('original_consensus_attributes', {})
                        
                        for k, v in ATTRIBUTE_DEFINITIONS.items():
                            # Default logic remains the same
                            default_val = original.get(k, v.get('default', v['options'][0]))
                            try:
                                idx = v['options'].index(default_val)
                            except ValueError:
                                idx = 0
                            audit_attrs[k] = st.selectbox(k, v['options'], index=idx, key=f"audit_{k}")
                        
                        if st.form_submit_button("Submit Audit"):
                            submit_request = {
                                **db_config,
                                "project_id": selected_project_id,
                                "audit_id": item['audit_id'],
                                "auditor_attributes": audit_attrs,
                                "auditor_id": ADJUDICATOR_NAME
                            }
                            result = api_call("audit/submit", data=submit_request)
                            if result:
                                st.success("Audit submitted!")
                                st.rerun()

    elif page == "Annotator Calibration (Metrics)":
        st.header(f"📊 Annotator Metrics (Project {selected_project_id})")
        
        request_data = {**db_config, "project_id": selected_project_id}
        tasks = api_call("metrics/annotator-tasks", data=request_data)
        
        if not tasks:
            st.warning("No adjudicated tasks available for this project.")
        else:
            annotators = sorted(list(set(t['assignee'] for t in tasks)))
            user = st.selectbox("Select Annotator", annotators)
            
            if st.button("Calculate Score"):
                user_tasks = [t['task_id'] for t in tasks if t['assignee'] == user]
                
                with st.spinner("Calculating Kappa scores..."):
                    metrics_request = {
                        **db_config,
                        "project_id": selected_project_id,
                        "annotator": user,
                        "task_ids": user_tasks
                    }
                    result = api_call("metrics/calculate-kappa", data=metrics_request)
                    
                    if result:
                        st.subheader(f"Results for {user}")
                        
                        attr_scores = result.get('attribute_scores', {})
                        df_scores = pd.DataFrame.from_dict(
                            attr_scores, 
                            orient='index', 
                            columns=['Kappa Score']
                        )
                        st.dataframe(df_scores, use_container_width=True)
                        
                        overall = result.get('overall_average', 0.0)
                        is_calibrated = result.get('is_calibrated', False)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Average Kappa", f"{overall:.3f}")
                        with col2:
                            if is_calibrated:
                                st.success("✅ Calibrated!")
                            else:
                                st.error("❌ Needs Training")
                        
                        # Threshold info
                        st.info("Calibration threshold: Kappa ≥ 0.85 (Cohen's Kappa is used to measure inter-annotator agreement vs. the Golden Set.)") 

    
    elif page == "Bulk Approval":
        st.header(f"✅ Bulk Approval (Project {selected_project_id})")
        
        request_data = {**db_config, "project_id": selected_project_id}
        solo_tasks = api_call("solo-tasks", data=request_data)
        
        if not solo_tasks:
            st.success("No pending solo tasks.")
        else:
            for user, tasks in solo_tasks.items():
                if st.button(f"Approve {len(tasks)} tasks for {user}"):
                    task_ids = [t['task_id'] for t in tasks]
                    approve_request = {
                        **db_config,
                        "project_id": selected_project_id,
                        "task_ids": task_ids
                    }
                    result = api_call("bulk-approve", data=approve_request)
                    if result:
                        st.success(f"Approved {len(tasks)} tasks!")
                        st.rerun()

    
    elif page == "Dataset Generation":
        st.header(f"📦 Dataset Generation (Project {selected_project_id})")
        
        st.info("Dataset will be generated from all approved and golden annotations for this project.")
        
        batches_response = api_call("batches", method="GET")
        
        if batches_response and 'batches' in batches_response:
            available_batches = batches_response['batches']
            
            st.subheader("Select Batch for Manifest")
            selected_batch = st.selectbox(
                "Batch (contains manifest.json)",
                available_batches,
                help="Select the batch folder that contains the manifest.json file"
            )
            
            output_filename = st.text_input(
                "Output CSV Filename",
                f"ava_dataset_project_{selected_project_id}.csv"
            )
            
            col1, col2 = st.columns(2)
            
            if 'manifest_data' not in st.session_state:
                st.session_state['manifest_data'] = {}

            with col1:
                if st.button("🔍 Preview Manifest"):
                    with st.spinner("Fetching manifest from S3..."):
                        manifest_request = {
                            **db_config,
                            "project_id": selected_project_id,
                            "batch_name": selected_batch
                        }
                        manifest_response = api_call("manifest/fetch", data=manifest_request)
                        
                        if manifest_response and manifest_response.get('status') == 'success':
                            st.success(f"✅ Found manifest with {manifest_response.get('keyframe_count', 0)} keyframes")
                            
                            
                            manifest_data = manifest_response.get('manifest_data', {})
                            if manifest_data:
                                st.json(dict(list(manifest_data.items())[:3])) 
                                st.session_state['manifest_data'] = manifest_data
                        else:
                            st.error("Failed to fetch manifest")
            
            with col2:
                if st.button("🚀 Generate Dataset"):
                    if not st.session_state.get('manifest_data'):
                        st.error("Please preview manifest first to load the data")
                    else:
                        with st.spinner("Generating AVA-format dataset..."):
                            generate_request = {
                                **db_config,
                                "project_id": selected_project_id,
                                "manifest_data": st.session_state['manifest_data'],
                                "output_filename": output_filename
                            }
                            
                            result = api_call("dataset/generate", data=generate_request)
                            
                            if result:
                                status = result.get('status')
                                
                                if status == 'success':
                                    st.success(f"✅ {result.get('message', 'Dataset generated')}")
                                    st.metric("Total Rows", result.get('rows_generated', 0))
                                    
                                    download_url = result.get('download_url')
                                    if download_url:
                                        st.markdown(f"### [⬇️ Download Dataset]({download_url})") 
                                        st.code(result.get('s3_key', ''), language='text')
                                        
                                    st.balloons()
                                elif status == 'warning':
                                    st.warning(result.get('message', 'No data available'))
                                else:
                                    st.error("Dataset generation failed")
        else:
            st.error("Could not fetch batches from S3")
        

        st.divider()
        st.subheader("Dataset Information")
        
        st.markdown("""
        **AVA-Kinetics Format:**
        - Combines approved solo annotations (80%) with golden adjudicated annotations (20%)
        - Each row represents one action label for one person in one frame
        - Action IDs are mapped from attribute values
        - Coordinates are normalized to [0, 1]
        
        **Columns:**
        - `video_id`: Source video identifier
        - `frame_timestamp`: Frame number in source video
        - `x1, y1, x2, y2`: Normalized bounding box coordinates
        - `action_id`: Mapped action identifier
        - `person_id`: Person track ID
        """)

