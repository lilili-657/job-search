"""In-memory PDF fixtures exercise the real parser without external services."""

from io import BytesIO
from contextlib import ExitStack
import unittest

from fastapi import UploadFile
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.app.models.resume import ResumeDocument
from backend.app.services.resume_ingestion import (
    CorruptPDFError,
    EncryptedPDFError,
    InvalidPDFError,
    NoExtractableTextError,
    ResumeIngestionError,
    ResumeIngestionService,
)


def make_pdf(*texts: str, encrypted: bool = False) -> bytes:
    """Build minimal text/blank pages using PDF's standard Helvetica font."""
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            })
            stream = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class ResumeIngestionTests(unittest.TestCase):
    def ingest_many(self, files: list[tuple[str, bytes]]) -> list[ResumeDocument]:
        with ExitStack() as stack:
            uploads = [
                UploadFile(file=stack.enter_context(BytesIO(data)), filename=name)
                for name, data in files
            ]
            return ResumeIngestionService().ingest_many(uploads)

    def test_batch_with_one_pdf_returns_list(self):
        documents = self.ingest_many([("Original Resume.PDF", make_pdf("My text"))])
        self.assertEqual(documents, [
            ResumeDocument(filename="Original Resume.PDF", extracted_text="My text")
        ])

    def test_batch_preserves_order_filenames_and_separate_text(self):
        documents = self.ingest_many([
            ("Z Resume.PDF", make_pdf("First resume", "Second page")),
            ("A Resume.pdf", make_pdf("Different resume")),
        ])
        self.assertEqual(documents, [
            ResumeDocument(
                filename="Z Resume.PDF", extracted_text="First resume\n\nSecond page"
            ),
            ResumeDocument(filename="A Resume.pdf", extracted_text="Different resume"),
        ])

    def test_batch_keeps_duplicate_filenames_as_separate_documents(self):
        documents = self.ingest_many([
            ("resume.pdf", make_pdf("First version")),
            ("resume.pdf", make_pdf("Second version")),
        ])
        self.assertEqual(documents, [
            ResumeDocument(filename="resume.pdf", extracted_text="First version"),
            ResumeDocument(filename="resume.pdf", extracted_text="Second version"),
        ])

    def test_batch_rejects_invalid_pdf_mixed_with_valid_pdfs(self):
        with self.assertRaises(InvalidPDFError) as caught:
            self.ingest_many([
                ("first.pdf", make_pdf("Valid first resume")),
                ("invalid.pdf", b"Not a PDF"),
                ("last.pdf", make_pdf("Valid last resume")),
            ])
        self.assertIn("Upload 2 ('invalid.pdf')", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, InvalidPDFError)

    def test_empty_batch_returns_empty_list(self):
        self.assertEqual(self.ingest_many([]), [])

    def ingest(self, data: bytes, filename: str | None = "resume.pdf"):
        with BytesIO(data) as stream:
            return ResumeIngestionService().ingest(
                UploadFile(file=stream, filename=filename)
            )

    def test_returns_only_filename_and_text_in_page_order(self):
        document = self.ingest(make_pdf("Alex Example", "Built useful tools"))
        self.assertIsInstance(document, ResumeDocument)
        self.assertEqual(document.model_dump(), {
            "filename": "resume.pdf",
            "extracted_text": "Alex Example\n\nBuilt useful tools",
        })

    def test_preserves_filename_and_upload_stream(self):
        with BytesIO(make_pdf("Original text")) as stream:
            stream.seek(7)
            upload = UploadFile(file=stream, filename="My Resume.PDF")
            service = ResumeIngestionService()
            first = service.ingest(upload)
            self.assertEqual(stream.tell(), 7)
            self.assertFalse(stream.closed)
            self.assertEqual(first, service.ingest(upload))
            self.assertEqual(first.filename, "My Resume.PDF")
            self.assertEqual(first.extracted_text, "Original text")

    def test_rejects_invalid_bytes_despite_pdf_filename(self):
        for data in (b"", b"This is not a PDF", b"<html>Not a PDF</html>"):
            with self.subTest(data=data), self.assertRaises(InvalidPDFError):
                self.ingest(data)

    def test_rejects_missing_filename(self):
        for filename in (None, "", "   "):
            with self.subTest(filename=filename), self.assertRaises(InvalidPDFError):
                self.ingest(make_pdf("Text"), filename=filename)

    def test_rejects_corrupt_and_truncated_pdf(self):
        for data in (b"%PDF-1.7\ncorrupt data\n%%EOF", make_pdf("Text")[:100]):
            with self.subTest(data=data), self.assertRaises(CorruptPDFError):
                self.ingest(data)

    def test_rejects_pdf_without_extractable_text(self):
        for data in (make_pdf(), make_pdf(""), make_pdf("   ")):
            with self.subTest(data=data), self.assertRaises(NoExtractableTextError):
                self.ingest(data)

    def test_keeps_text_when_other_pages_are_blank(self):
        self.assertEqual(
            self.ingest(make_pdf("", "Readable text", "")).extracted_text,
            "Readable text",
        )

    def test_rejects_encrypted_pdf(self):
        with self.assertRaises(EncryptedPDFError):
            self.ingest(make_pdf("Private text", encrypted=True))

    def test_closed_upload_has_explicit_error(self):
        stream = BytesIO(b"data")
        stream.close()
        with self.assertRaises(ResumeIngestionError):
            ResumeIngestionService().ingest(UploadFile(file=stream, filename="resume.pdf"))


if __name__ == "__main__":
    unittest.main()
