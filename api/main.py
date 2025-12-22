from fastapi import FastAPI
from .routers.cvat_task_creator import router as task_router
from .routers.qc_router import router as qc_router

app = FastAPI(title="AVA CVAT Platform")

app.include_router(
    task_router,
    prefix="/api/v1/cvat",
    tags=["Task Creator"],
)

app.include_router(
    qc_router,
    prefix="/api/v1/qc",
    tags=["QC"],
)
