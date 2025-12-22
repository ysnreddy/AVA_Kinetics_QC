from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import json
import boto3
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import pandas as pd
import logging
import io
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from processing_pipeline.services.label_loader import load_cvat_labels
from processing_pipeline.services.dataset_generator import DatasetGenerator
from processing_pipeline.services.qc_service import QCService
    



logger = logging.getLogger(__name__)

router = APIRouter()

AWS_REGION = "us-east-1"
S3_BUCKET = "ava-new-kinetics"
s3_client = boto3.client("s3", region_name=AWS_REGION)

def get_backend_attribute_config():
    """Returns attribute list and definitions from YAML"""
    labels = load_cvat_labels()
    person_label = next((l for l in labels if l["name"] == "person"), None)
    if not person_label:
        return [], {}
    
    attr_names = [attr["name"] for attr in person_label["attributes"]]
    attr_defs = {attr["name"]: attr["values"] for attr in person_label["attributes"]}
    return attr_names, attr_defs



class DBConfig(BaseModel):
    dbname: str
    user: str
    password: str
    host: str
    port: str

class ProjectRequest(DBConfig):
    project_id: int


class KeyframeRequest(ProjectRequest):
    task_id_a: int
    task_id_b: int
    keyframe_name: str

class KeyframeURLRequest(ProjectRequest):
    batch_name: str
    keyframe_name: str

class GoldenAnnotationRequest(ProjectRequest):
    task_id_a: int
    task_id_b: int
    keyframe_name: str
    person_id: int
    xtl: float
    ytl: float
    xbr: float
    ybr: float
    attributes: Dict[str, Any]
    adjudicator: str

class AuditSubmissionRequest(ProjectRequest):
    audit_id: int
    auditor_attributes: Dict[str, Any]
    auditor_id: str

class BatchCompleteRequest(ProjectRequest):
    task_id_a: int
    task_id_b: int

class BulkApproveRequest(ProjectRequest):
    task_ids: List[int]

class MetricsRequest(ProjectRequest):
    annotator: str
    task_ids: List[int]

class DatasetGenerateRequest(ProjectRequest):
    manifest_data: Dict[str, Any]
    output_filename: str = "final_ava.csv"

class ManifestUploadRequest(ProjectRequest):
    batch_name: str


def run_query(db: DBConfig, query: str, params=None, fetch="all"):
    """Execute database query with error handling"""
    try:
        conn = psycopg2.connect(
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            host=db.host,
            port=int(db.port),
        )
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch == "all":
                res = cur.fetchall()
            elif fetch == "one":
                res = cur.fetchone()
            else:
                res = None
            conn.commit()
        conn.close()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def list_s3_batches():
    """List all batch folders in S3 bucket"""
    try:
        result = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Delimiter='/'
        )
        batches = [p['Prefix'].rstrip('/') for p in result.get('CommonPrefixes', [])]
        return batches
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 list error: {str(e)}")

def generate_presigned_url(folder_prefix: str, file_name: str, expiry: int = 3600):
    """Generate presigned URL for a specific S3 Key"""
    if folder_prefix == "datasets":
        s3_key = f"{folder_prefix}/{file_name}"
    else:
        s3_key = f"{folder_prefix}/keyframes/{file_name}" 
        
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=expiry
        )
        return url
    except Exception as e:
        logger.error(f"S3 presigned URL error for key {s3_key}: {e}")
        raise HTTPException(status_code=500, detail=f"S3 presigned URL error: {str(e)}")

def list_keyframes_in_batch(batch_name: str):
    """List all keyframes in a batch folder"""
    try:
        prefix = f"{batch_name}/keyframes/"
        result = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=prefix
        )
        keyframes = []
        if 'Contents' in result:
            for obj in result['Contents']:
                key = obj['Key']
                if key.startswith(prefix) and key != prefix:
                    filename = key[len(prefix):]
                    keyframes.append(filename)
        return keyframes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 list keyframes error: {str(e)}")

# ================= ENDPOINTS =================

@router.post("/projects")
def get_projects(db: DBConfig):
    return run_query(db, "SELECT project_id, name FROM projects ORDER BY project_id DESC")

@router.get("/batches")
def get_batches():
    batches = list_s3_batches()
    return {"batches": batches}

@router.post("/batches/{batch_name}/keyframes")
def get_batch_keyframes(batch_name: str):
    keyframes = list_keyframes_in_batch(batch_name)
    return {"batch_name": batch_name, "keyframes": keyframes}

@router.post("/keyframe-url")
def get_keyframe_url(req: KeyframeURLRequest):
    url = generate_presigned_url(req.batch_name, req.keyframe_name)
    return {"url": url, "batch_name": req.batch_name, "keyframe_name": req.keyframe_name}

@router.post("/adjudication/pairs")
def get_adjudication_pairs(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    tasks = run_query(db, """ SELECT task_id, name, assignee, qc_status, project_id FROM tasks WHERE project_id = %s ORDER BY name """, (req.project_id,))
    
    tasks_by_batch = defaultdict(list)
    for task in tasks:
        batch_name = '_'.join(task['name'].split('_')[:-1]) if '_' in task['name'] else task['name']
        tasks_by_batch[batch_name].append(task)
    
    overlap_pairs = []
    for batch_name, task_list in tasks_by_batch.items():
        pending_adj = [t for t in task_list if t['qc_status'] == 'pending_adjudication']
        for i in range(0, len(pending_adj), 2):
            if i + 1 < len(pending_adj):
                t1, t2 = pending_adj[i], pending_adj[i + 1]
                overlap_pairs.append({
                    "task_id_A": t1['task_id'], "task_id_B": t2['task_id'],
                    "name_A": t1['name'], "name_B": t2['name'],
                    "assignee_A": t1['assignee'], "assignee_B": t2['assignee'],
                    "clip_name": batch_name, "project_id": t1['project_id'], "status": "Pending Review"
                })
    return overlap_pairs

@router.post("/adjudication/common-keyframes")
def get_common_keyframes(req: KeyframeRequest):
    db = DBConfig(**req.dict(exclude={"project_id", "task_id_a", "task_id_b", "keyframe_name"}))
    results = run_query(db, 
        """
        SELECT keyframe_name FROM annotations WHERE task_id = %s
        INTERSECT
        SELECT keyframe_name FROM annotations WHERE task_id = %s
        """, (req.task_id_a, req.task_id_b)
    )
    return [row['keyframe_name'] for row in results]

@router.post("/adjudication/annotations")
def get_adjudication_annotations(req: KeyframeRequest):
    db = DBConfig(**req.dict(exclude={"project_id", "task_id_a", "task_id_b", "keyframe_name"}))
    results = run_query(db,
        """
        (SELECT task_id, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s)
        UNION ALL
        (SELECT task_id, person_id, xtl, ytl, xbr, ybr, attributes FROM annotations WHERE task_id = %s AND keyframe_name = %s)
        """,
        (req.task_id_a, req.keyframe_name, req.task_id_b, req.keyframe_name)
    )
    return results

@router.post("/adjudication/save-golden")
def save_golden_annotation(req: GoldenAnnotationRequest):
    """
    Saves adjudicated golden annotation.
    FIX: Uses 'original_project_id' as per the final schema.
    """
    db = DBConfig(**req.dict(exclude={
        "project_id", "task_id_a", "task_id_b", "keyframe_name", 
        "person_id", "xtl", "ytl", "xbr", "ybr", "attributes", "adjudicator"
    }))
    
    run_query(
        db,
        """
        INSERT INTO golden_annotations
        (original_project_id, original_task_id_A, original_task_id_B, 
         keyframe_name, person_id, xtl, ytl, xbr, ybr, attributes, 
         adjudicated_by, adjudicated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (keyframe_name, person_id) 
        DO UPDATE SET
            attributes = EXCLUDED.attributes,
            adjudicated_by = EXCLUDED.adjudicated_by,
            adjudicated_at = CURRENT_TIMESTAMP
        """,
        (
            req.project_id, req.task_id_a, req.task_id_b, 
            req.keyframe_name, req.person_id,
            req.xtl, req.ytl, req.xbr, req.ybr,
            json.dumps(req.attributes), req.adjudicator
        ),
        fetch=None
    )
    return {"status": "success", "message": "Golden annotation saved"}

@router.post("/adjudication/mark-complete")
def mark_batch_complete(req: BatchCompleteRequest):
    db = DBConfig(**req.dict(exclude={"project_id", "task_id_a", "task_id_b"}))
    run_query(db, "UPDATE tasks SET qc_status='review_complete' WHERE task_id IN (%s, %s)",
              (req.task_id_a, req.task_id_b), fetch=None)
    return {"status": "success", "message": "Batch marked as complete"}


@router.post("/audit/pending")
def get_pending_audits(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    return run_query(db, 
        """
        SELECT task_id, name, qc_status 
        FROM tasks 
        WHERE qc_status = 'pending_audit' AND project_id = %s 
        ORDER BY name
        """, (req.project_id,)
    )

@router.post("/audit/items")
def get_audit_items(req: ProjectRequest):
    """FIX: Query only audits where the task is part of the current project (via JOIN)."""
    db = DBConfig(**req.dict(exclude={"project_id"}))
    return run_query(db, 
        """
        SELECT a.*, t.name as task_name
        FROM audits a
        JOIN tasks t ON a.task_id = t.task_id
        WHERE a.is_overturn IS NULL AND t.project_id = %s
        """, (req.project_id,)
    )

@router.post("/audit/submit")
def submit_audit(req: AuditSubmissionRequest):
    db = DBConfig(**req.dict(exclude={
        "project_id", "audit_id", "auditor_attributes", "auditor_id"
    }))
    
    audit = run_query(db, "SELECT original_consensus_attributes FROM audits WHERE audit_id = %s", (req.audit_id,), fetch="one")
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    is_overturn = (req.auditor_attributes != audit['original_consensus_attributes'])
    
    run_query(db,
        """ UPDATE audits SET auditor_attributes=%s, is_overturn=%s, auditor_id=%s WHERE audit_id=%s """,
        (json.dumps(req.auditor_attributes), is_overturn, req.auditor_id, req.audit_id),
        fetch=None
    )
    return {"status": "success", "is_overturn": is_overturn}

@router.post("/audit/stats")
def get_audit_stats(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    return run_query(db, 
        """
        SELECT a.is_overturn, t.name 
        FROM audits a 
        JOIN tasks t ON a.task_id = t.task_id 
        WHERE a.is_overturn IS NOT NULL AND t.project_id = %s
        """, (req.project_id,)
    )

@router.post("/audit/finalize")
def finalize_audit(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    run_query(db, "UPDATE tasks SET qc_status='approved' WHERE qc_status='pending_audit' AND project_id=%s", (req.project_id,), fetch=None)
    return {"status": "success", "message": "Batch approved"}

@router.post("/audit/reject")
def reject_batch(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    run_query(db, "UPDATE tasks SET qc_status='rejected' WHERE (qc_status='pending_audit' OR qc_status='approved') AND project_id=%s", (req.project_id,), fetch=None)
    return {"status": "success", "message": "Batch rejected"}

@router.post("/metrics/annotator-tasks")
def get_annotator_tasks(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    return run_query(db, "SELECT task_id, name, assignee FROM tasks WHERE qc_status = 'review_complete' AND project_id = %s", (req.project_id,))

@router.post("/bulk-approve")
def bulk_approve(req: BulkApproveRequest):
    db = DBConfig(**req.dict(exclude={"project_id", "task_ids"}))
    run_query(db, "UPDATE tasks SET qc_status='approved' WHERE task_id = ANY(%s)", (req.task_ids,), fetch=None)
    return {"status": "success", "approved_count": len(req.task_ids)}

@router.post("/solo-tasks")
def get_solo_tasks(req: ProjectRequest):
    db = DBConfig(**req.dict(exclude={"project_id"}))
    tasks = run_query(db, "SELECT task_id, name, assignee FROM tasks WHERE qc_status = 'pending' AND project_id = %s ORDER BY assignee, name", (req.project_id,))
    
    by_annotator = defaultdict(list)
    for task in tasks:
        by_annotator[task['assignee']].append(task)
    
    return dict(by_annotator)



@router.post("/metrics/calculate-kappa")
def calculate_annotator_kappa(req: MetricsRequest):
    """Calculate kappa scores for an annotator across multiple tasks"""
    db = DBConfig(**req.dict(exclude={"project_id", "annotator", "task_ids"}))
    
    attr_names, _ = get_backend_attribute_config()
    
    if not attr_names:
        raise HTTPException(status_code=500, detail="Label configuration could not be loaded")

    qc_service = QCService(db.dict(), req.project_id) 
    all_scores = defaultdict(list)
    
    for task_id in req.task_ids:
        scores = qc_service.calculate_kappa_vs_golden(task_id, attr_names)
        for attr, score in scores.items():
            all_scores[attr].append(score)
    
    avg_scores = {attr: sum(scores) / len(scores) for attr, scores in all_scores.items() if scores}
    overall_avg = sum(avg_scores.values()) / len(avg_scores) if avg_scores else 0.0
    
    return {
        "annotator": req.annotator, 
        "attribute_scores": avg_scores,
        "overall_average": overall_avg, 
        "is_calibrated": overall_avg >= 0.85
    }


@router.post("/dataset/generate")
def generate_dataset(req: DatasetGenerateRequest):
    """Generates AVA-Kinetics CSV from approved/golden annotations"""
    db = DBConfig(**req.dict(exclude={"project_id", "manifest_data", "output_filename"}))
    
    try:
        
        generator = DatasetGenerator(db.dict(), req.project_id)
        
        csv_buffer, rows_generated = generator.generate_ava_csv_in_memory(req.manifest_data)
        
        if rows_generated == 0:
             return { "status": "warning", "message": "No approved or golden annotations found.", "rows_generated": 0 }

        s3_key = f"datasets/project_{req.project_id}/{req.output_filename}"
        
        s3_client.put_object(
            Bucket=S3_BUCKET, Key=s3_key, Body=csv_buffer, ContentType='text/csv'
        )
        
        download_url = generate_presigned_url("datasets", f"project_{req.project_id}/{req.output_filename}")
        
        return {
            "status": "success", "message": f"Generated {rows_generated} rows",
            "rows_generated": rows_generated, "download_url": download_url, "s3_key": s3_key
        }
        
    except Exception as e:
        logger.error(f"Dataset generation critical error: {e}")
        raise HTTPException(status_code=500, detail=f"Dataset generation failed: {str(e)}")

@router.post("/manifest/fetch")
def fetch_manifest_from_s3(req: ManifestUploadRequest):
    """Fetch manifest.json from S3 batch folder (uses corrected path)"""
    db = DBConfig(**req.dict(exclude={"project_id", "batch_name"}))
    
    try:
        s3_key = f"{req.batch_name}/manifest/manifest.json" 
        
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        manifest_content = response['Body'].read().decode('utf-8')
        manifest_data = json.loads(manifest_content)
        
        return {
            "status": "success", "batch_name": req.batch_name,
            "manifest_data": manifest_data, "keyframe_count": len(manifest_data)
        }
        
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"Manifest not found for batch {req.batch_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))