from fastapi import APIRouter
from api.schemas import JobRequest, JobStatus

router = APIRouter()


@router.post("/jobs", response_model=JobStatus)
def create_job(payload: JobRequest):
    return JobStatus(
        job_id="job-1",
        status="pending",
        retry_count=0,
        breaking_change_count=0,
        affected_file_count=0,
    )
