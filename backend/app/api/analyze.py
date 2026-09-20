from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models.analysis import AnalyzeDebugResponse

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalyzeDebugResponse)
def analyze(
    job_url: Annotated[str, Form()],
    resumes: Annotated[list[UploadFile], File(min_length=1)],
    additional_notes: Annotated[str, Form()] = "",
) -> AnalyzeDebugResponse:
    if not job_url.strip():
        raise HTTPException(status_code=422, detail="job_url must not be empty.")

    resume_names: list[str] = []
    for resume in resumes:
        # Validate metadata only. Do not read or inspect the file contents.
        if (
            not resume.filename
            or not resume.filename.lower().endswith(".pdf")
            or resume.content_type != "application/pdf"
        ):
            raise HTTPException(
                status_code=422,
                detail="Resumes must have a .pdf filename and application/pdf content type.",
            )
        resume_names.append(resume.filename)

    return AnalyzeDebugResponse(
        job_url=job_url,
        resume_count=len(resumes),
        resume_names=resume_names,
        notes_length=len(additional_notes),
    )
