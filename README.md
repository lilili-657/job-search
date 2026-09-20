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
No URL fetching, resume parsing, or AI analysis is implemented.
