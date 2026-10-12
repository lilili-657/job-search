# Job Search

Minimal Next.js + TypeScript frontend and FastAPI backend.
Requires Node.js 20.9+ and Python 3.10+.

## Run locally

From the repository root, start the backend:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 to enter a job URL, select multiple PDF resumes,
and add notes. Selected filenames appear with a Remove button for each file.
**Analyze Fit** uploads the form to `http://localhost:8000/api/analyze` and
displays the debug JSON response. Run both servers to submit the form.
The form is disabled while submitting and displays errors if the request fails.
Before sending a request, it requires a nonblank job URL and at least one PDF
resume. Invalid file selections are rejected with a message. PDF selection
checks both the filename extension and declared file type. FastAPI independently
validates these inputs, including requests that bypass the frontend.

The form keeps `jobUrl` and `additionalNotes` as strings and `resumeFiles` as
browser `File` objects in React state. A `File` provides metadata and access
to the selected file's contents; a filename string alone does not.
Submitting uploads the files, URL text, and notes; the backend returns metadata
without inspecting file contents. No job URL is fetched and no analysis occurs.
Refreshing the page clears the form. There are no structured job or candidate
profiles yet.

You can also check the backend directly:

```sh
curl http://localhost:8000/health
```

To check the frontend production build, run `npm run build` in `frontend/`.

## Frontend structure

Voice recording sits beside Additional Notes (stacked on narrow screens).
Record requests microphone permission; Stop finishes the recording and releases
the microphone. The UI shows elapsed duration and offers local playback, Delete
recording, and Re-record. Re-record replaces the previous recording once a new
recording successfully starts. Cancel dismisses the pending request in the app;
if permission arrives afterward, that microphone stream is immediately released.

`app/voice-recorder.tsx` keeps the audio `Blob` in React state. A temporary object
URL enables playback and is revoked when replaced, deleted, or unmounted.
Recordings disappear from frontend state on refresh/navigation. The Transcribe
button sends the Blob to `/api/transcribe` using `FormData`. The backend forwards
it to OpenAI and returns `{ "text": "..." }`. The transcript is appended to the
latest Additional Notes value, including edits made while the request was in
flight. Notes remain manually editable, and analysis never runs automatically.
Successful transcription clears the local Blob and releases its playback URL;
failures keep the recording available for retry. Analyze Fit remains disabled
while recording, requesting microphone access, or transcribing.

Recording uses [MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
and requires microphone access on HTTPS or localhost. The browser chooses its
supported audio format. Permission and recording failures appear next to the controls.

Manual browser check: Record and allow access, speak for a few seconds, Stop,
confirm duration and playback, Re-record, then Delete recording. Also deny access
and cancel a pending permission request. Confirm typed notes stay unchanged and
Analyze Fit's network request contains only its existing URL, notes, and PDFs.
Click Transcribe and confirm a separate multipart request contains one `audio`
file, the transcript is appended to Additional Notes, and no `/api/analyze`
request is made. Edit notes while waiting and confirm those edits remain. Check
that transcription failures keep the recording available and preserve notes.

```text
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
└── lib/
    └── api.ts
```

`page.tsx` owns form, loading, error, and result state. `lib/api.ts` builds
`FormData`, posts it, and parses `AnalyzeDebugResponse`. The exact keys are
`job_url`, `additional_notes`, and repeated `resumes` entries (one per file),
matching FastAPI's arguments. The browser sets the multipart boundary.

## Backend structure

```text
backend/
└── app/
    ├── __init__.py
    ├── main.py
    ├── api/
    │   ├── __init__.py
    │   └── analyze.py
    └── models/
        ├── __init__.py
        └── analysis.py
```

`main.py` creates the app, configures CORS, registers the analyze router, and
defines `/health`. `api/analyze.py` handles the analyze endpoint and validation.
`models/analysis.py` defines its response model. The empty `__init__.py` files
mark Python packages.

## Speech-to-text endpoint

`POST /api/transcribe` accepts one uploaded file in multipart field `audio` and
returns `{ "text": "..." }`. The backend uses the current
[OpenAI file transcription API](https://developers.openai.com/api/docs/guides/speech-to-text)
with `gpt-transcribe`, `response_format=json`, and the existing Requests client.
No additional SDK is required. It transcribes in the spoken language.

Set `OPENAI_API_KEY` in the backend process environment before starting Uvicorn.
For example, in the project's zsh terminal (input is hidden):

```sh
read -s 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
python -m uvicorn backend.app.main:app --reload --port 8000
```

The key is read only on the server. Do not put it in frontend code or a
`NEXT_PUBLIC_` variable. `.env` is ignored by Git, but this app does not
implicitly load it. A missing key returns HTTP 503 without contacting OpenAI.

The route rejects empty files and unsupported extensions with HTTP 422 and files
larger than 25,000,000 bytes with HTTP 413. Supported extensions are FLAC, MP3,
MP4, MPEG, MPGA, M4A, OGG, WAV, and WebM. OpenAI validates the actual audio.
Requests have a 10-second connection timeout and a 90-second read timeout, with
no automatic retries. Provider errors are sanitized: timeouts return 504,
connection/provider failures 502, authentication/configuration failures 503,
and rate limits 429. Empty transcripts or rejected audio return 422.

The backend closes the temporary upload stream in all cases and creates no
permanent audio files, cache entries, or database records. FastAPI may spool an
upload to temporary disk during the request. Audio is sent to OpenAI for processing;
local cleanup does not define the provider's data-retention policy.

```sh
curl http://localhost:8000/api/transcribe -F 'audio=@recording.webm;type=audio/webm'
```

Install `requirements-dev.txt` for backend HTTP tests, then run:

```sh
python -m unittest discover -s backend/tests -p 'test_transcribe.py' -v
cd frontend
node --test tests/audio-api.test.mjs
```

Tests mock the OpenAI HTTP call; they do not need a real API key or send audio
externally. A live transcription check requires a configured backend key and
recording in the browser.

## Analyze debug endpoint

`POST /api/analyze` accepts multipart form fields: required `job_url`, optional
`additional_notes` (defaults to an empty string), and one or more files under
the repeated field name `resumes`.

```sh
curl http://localhost:8000/api/analyze \
  -F 'job_url=https://example.com/jobs/role' \
  -F 'additional_notes=Interested in this role.' \
  -F 'resumes=@/path/to/resume.pdf;type=application/pdf' \
  -F 'resumes=@/path/to/another.pdf;type=application/pdf'
```

Replace the example paths with your own files. The response is:

```json
{
  "job_url": "https://example.com/jobs/role",
  "resume_count": 2,
  "resume_names": ["resume.pdf", "another.pdf"],
  "notes_length": 24
}
```

Missing or blank URLs, missing resumes, and non-PDF metadata return HTTP 422.
PDF validation checks a case-insensitive `.pdf` filename extension and the
declared `application/pdf` content type only. File contents are not inspected,
so this does not verify that the bytes are actually a PDF. Notes length is the
number of characters, including whitespace; omitted notes have length zero.

FastAPI reads text through `Form()` and files through `UploadFile`/`File()`;
no separate request model is needed. `AnalyzeDebugResponse` defines the returned
JSON. Multipart parsing requires `python-multipart` (see the
[FastAPI documentation](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/)).
This endpoint does not fetch URLs, parse resumes, or perform AI analysis.

## Isolated job page retrieval

`backend/app/services/job_page_fetcher.py` provides `JobPageFetcher`, using
[Requests](https://requests.readthedocs.io/en/latest/user/quickstart/).
It is not connected to `/api/analyze`.

```python
from backend.app.services.job_page_fetcher import JobPageFetcher

result = JobPageFetcher(timeout_seconds=10).fetch("https://example.com/jobs/role")
print(result.raw_html)
print(result.status_code)
print(result.final_url)
```

Redirects are followed automatically. Non-200 responses retain their body,
status, and final URL rather than raising an HTTP status error. Timeouts raise
`JobPageFetchTimeout`; other request failures (including redirect loops and
invalid URLs) raise `JobPageFetchError`. The timeout applies to connection and
read inactivity, not the total duration of a download.

`raw_html` is decoded response text without parsing or semantic extraction.
It may be an error page or non-HTML content. Fetching does not run JavaScript,
identify job titles, companies, or requirements, or use OpenAI.

After installing `requirements.txt`, run the isolated tests from the repository
root. They use a local HTTP server and do not contact external job sites:

```sh
python -m unittest discover -s backend/tests -v
```

## Isolated HTML text extraction

`backend/app/services/html_text_extractor.py` provides
`extract_visible_text(raw_html: str) -> str`, using
[Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/#get-text)
with Python's `html.parser` explicitly selected.

```python
from backend.app.services.html_text_extractor import extract_visible_text

text = extract_visible_text("<p>Build <b>useful</b> tools.</p><script>code()</script>")
assert text == "Build useful tools."
```

The extractor removes `script`, `style`, `head`, `template`, and elements with
the `hidden` attribute. Comments are omitted. It decodes HTML entities, keeps
text in document order, and collapses whitespace to single spaces. Spacing is
basic and does not preserve page layout. CSS visibility and JavaScript rendering
are not evaluated. No LLM is used and no company or job requirements are inferred.
The fetcher and `/api/analyze` remain unchanged.

Run just the extraction tests without a server or network access:

```sh
python -m unittest discover -s backend/tests -p 'test_html_text_extractor.py' -v
```

## Isolated resume ingestion

`ResumeIngestionService.ingest(upload)` accepts one FastAPI `UploadFile` and
returns `ResumeDocument(filename: str, extracted_text: str)`. The service lives
in `backend/app/services/resume_ingestion.py`; the model is in
`backend/app/models/resume.py`. It is not connected to `/api/analyze`.

For multiple PDFs, use `ResumeIngestionService.ingest_many(uploads)` with a
`list[UploadFile]`. It returns `list[ResumeDocument]` in the original upload
order. Each document retains its original filename and its own extracted text;
text is never combined across resumes. Duplicate filenames remain separate list
entries, and an empty upload list returns `[]`. The single-file `ingest` method
remains available.

```python
service = ResumeIngestionService()
documents = service.ingest_many(uploads)
for document in documents:
    print(document.filename, document.extracted_text)
```

Batch ingestion fails on the first invalid, corrupt, encrypted, or textless PDF.
The error retains its specific type and includes the upload's one-based position
and original filename. No partial list is returned; later uploads are not read.

Keeping filename and text together preserves document provenance: future
evidence can be traced to the supporting resume, citations can name its source,
and future RAG chunks can carry that source with them. Filenames are not unique
identifiers; persistent citations or RAG would also need document IDs and more
precise locations such as pages. Those capabilities are not implemented here.

The synchronous service reads the upload from the beginning, restores its stream
position, and leaves it open for the caller. It checks the PDF header and uses
[`pypdf`](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) with strict
parsing to extract the existing text layer. Nonempty page texts are joined in
page order with blank lines. It does not infer reading order for complex layouts.
Async callers should run ingestion in a worker thread.

All ingestion errors inherit from `ResumeIngestionError`:

- `InvalidPDFError`: missing filename, empty bytes, or missing PDF header.
- `CorruptPDFError`: PDF parsing or text extraction failed; no partial result.
- `EncryptedPDFError`: encrypted PDFs are unsupported.
- `NoExtractableTextError`: no non-whitespace text was extracted, including
  blank or image-only PDFs. OCR is not performed.

Filename and MIME type do not prove that the contents are a PDF. Strict parsing
can reject malformed PDFs that a viewer might repair. Extracted text is not a
semantic resume profile: no OpenAI, skill inference, embeddings, or RAG is used.

After installing `requirements.txt`, run the isolated in-memory PDF tests:

```sh
python -m unittest discover -s backend/tests -p 'test_resume_ingestion.py' -v
```
