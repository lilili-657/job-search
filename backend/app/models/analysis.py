from pydantic import BaseModel


class AnalyzeDebugResponse(BaseModel):
    job_url: str
    resume_count: int
    resume_names: list[str]
    notes_length: int
