from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import boto3

from processing_pipeline.services.cvat_integration import CVATClient

router = APIRouter()


class ListBatchesRequest(BaseModel):
    s3_bucket: str


class ListZipsRequest(BaseModel):
    s3_bucket: str
    batch_name: str


class CreateTasksRequest(BaseModel):
    host: str
    username: str
    password: str
    s3_bucket: str
    project_name: str
    batch_name: str
    zip_files: List[str]
    annotators: Optional[List[str]] = []
    annotation_base_path: str   # ✅ NEW


def get_s3_client():
    return boto3.client("s3")

@router.post("/list-batches")
def list_batches(req: ListBatchesRequest):
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")

    batches = set()
    for page in paginator.paginate(
        Bucket=req.s3_bucket,
        Delimiter="/",
    ):
        for p in page.get("CommonPrefixes", []):
            batches.add(p["Prefix"].rstrip("/"))

    return {"batches": sorted(batches)}


@router.post("/list-frames-zips")
def list_frame_zips(req: ListZipsRequest):
    s3 = get_s3_client()
    prefix = f"{req.batch_name}/frames_zip/"

    paginator = s3.get_paginator("list_objects_v2")
    zips = []

    for page in paginator.paginate(
        Bucket=req.s3_bucket,
        Prefix=prefix,
    ):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".zip"):
                zips.append(obj["Key"].split("/")[-1])

    return {"zip_files": sorted(zips)}


@router.post("/create-project-tasks")
def create_project_and_tasks(req: CreateTasksRequest):
    try:
        client = CVATClient(
            host=req.host,
            username=req.username,
            password=req.password,
            s3_bucket=req.s3_bucket,
            annotation_base_path=req.annotation_base_path,
        )

        result = client.create_project_and_add_tasks_from_s3(
            project_name=req.project_name,
            batch_name=req.batch_name,
            zip_files=req.zip_files,
            annotators=req.annotators,
        )

        return {
            "message": "Tasks created successfully",
            "tasks_created": result["tasks_created"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
