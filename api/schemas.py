from pydantic import BaseModel


class JobRequest(BaseModel):
    repo_path: str
    dep_name: str
    old_version: str
    new_version: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    retry_count: int
    breaking_change_count: int
    affected_file_count: int
