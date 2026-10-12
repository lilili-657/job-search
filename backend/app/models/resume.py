from pydantic import BaseModel


class ResumeDocument(BaseModel):
    """An ingested document, without inferred candidate information."""

    filename: str
    extracted_text: str
