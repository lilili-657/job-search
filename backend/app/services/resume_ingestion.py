"""Deterministic extraction of an uploaded PDF's existing text layer."""

from io import BytesIO

from fastapi import UploadFile
from pypdf import PdfReader

from ..models.resume import ResumeDocument


class ResumeIngestionError(Exception):
    """The upload could not be ingested."""


class InvalidPDFError(ResumeIngestionError):
    """The upload is empty, missing a filename, or not a PDF."""


class CorruptPDFError(ResumeIngestionError):
    """The PDF cannot be parsed or its text cannot be read."""


class EncryptedPDFError(ResumeIngestionError):
    """Encrypted PDFs are not supported by this service."""


class NoExtractableTextError(ResumeIngestionError):
    """The PDF has no non-whitespace text layer; OCR is not performed."""


class ResumeIngestionService:
    def ingest_many(self, uploads: list[UploadFile]) -> list[ResumeDocument]:
        """Return separate documents in upload order, or fail on the first error.

        Empty input returns an empty list. Errors retain their specific type
        and identify the failing upload by its one-based position and filename.
        No partial list is returned and later uploads are not processed.
        """
        documents: list[ResumeDocument] = []
        for position, upload in enumerate(uploads, start=1):
            try:
                documents.append(self.ingest(upload))
            except ResumeIngestionError as exc:
                raise type(exc)(
                    f"Upload {position} ({upload.filename!r}): {exc}"
                ) from exc
        return documents

    def ingest(self, upload: UploadFile) -> ResumeDocument:
        """Read one upload synchronously without closing or consuming its stream.

        Suitable for synchronous callers, including FastAPI's sync handlers.
        Async callers should run this blocking operation in a worker thread.
        """
        if not upload.filename or not upload.filename.strip():
            raise InvalidPDFError("The uploaded PDF must have a filename.")

        try:
            position = upload.file.tell()
            try:
                upload.file.seek(0)
                raw_bytes = upload.file.read()
            finally:
                upload.file.seek(position)
        except (OSError, ValueError) as exc:
            raise ResumeIngestionError("Unable to read the uploaded file.") from exc

        # Inspect actual bytes rather than trusting the extension or MIME type.
        if not raw_bytes.startswith(b"%PDF-"):
            raise InvalidPDFError("The upload is empty or has no valid PDF header.")

        try:
            reader = PdfReader(BytesIO(raw_bytes), strict=True)
            if reader.is_encrypted:
                raise EncryptedPDFError("Encrypted PDFs are not supported.")
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except EncryptedPDFError:
            raise
        except Exception as exc:
            # Malformed PDFs can also trigger low-level parsing exceptions.
            # Keep this boundary limited to the third-party parser/extractor.
            raise CorruptPDFError("The PDF is corrupt or cannot be read.") from exc

        extracted_text = "\n\n".join(text for text in pages if text)
        if not extracted_text:
            raise NoExtractableTextError(
                "The PDF contains no extractable text. OCR is not performed."
            )

        return ResumeDocument(
            filename=upload.filename,
            extracted_text=extracted_text,
        )
