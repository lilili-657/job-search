"use client";

import { useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { analyzeFit as requestAnalysis } from "../lib/api";
import type { AnalyzeDebugResponse } from "../lib/api";

export default function Home() {
  const [jobUrl, setJobUrl] = useState<string>("");
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [additionalNotes, setAdditionalNotes] = useState<string>("");
  const [result, setResult] = useState<AnalyzeDebugResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const [jobUrlError, setJobUrlError] = useState("");
  const [fileError, setFileError] = useState("");

  function isPdf(file: File) {
    return /\.pdf$/i.test(file.name) && file.type === "application/pdf";
  }

  function selectResumes(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    if (selected.length === 0) return;
    // Match the backend's metadata checks without inspecting file contents.
    const pdfs = selected.filter(isPdf);
    const rejected = selected.filter((file) => !isPdf(file));
    setResumeFiles((previous) => [...previous, ...pdfs]);
    setFileError(
      rejected.length > 0
        ? `Not added: ${rejected.map((file) => file.name).join(", ")}. Choose PDF files with a .pdf extension and application/pdf file type.`
        : "",
    );
    // Allow a removed file to be selected again using the same picker.
    event.target.value = "";
  }

  async function analyzeFit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;

    const urlMessage = jobUrl.trim() ? "" : "Enter a job URL.";
    const resumeMessage = resumeFiles.length === 0
      ? "Select at least one PDF resume."
      : resumeFiles.every(isPdf)
        ? ""
        : "All resumes must be PDF files with a .pdf extension and application/pdf file type.";
    setJobUrlError(urlMessage);
    setFileError(resumeMessage);
    setError("");
    setResult(null);
    if (urlMessage || resumeMessage) return;

    submitting.current = true;
    setIsLoading(true);
    try {
      setResult(await requestAnalysis(jobUrl, resumeFiles, additionalNotes));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    } finally {
      submitting.current = false;
      setIsLoading(false);
    }
  }

  return (
    <main>
      <h1>Job Search</h1>
      <p>Add a job URL, your resumes, and any additional context.</p>
      <form onSubmit={analyzeFit} aria-busy={isLoading} noValidate>
        <fieldset disabled={isLoading}>
          <div className="field">
            <label htmlFor="job-url">Job URL</label>
            <input
              id="job-url"
              type="text"
              required
              aria-invalid={Boolean(jobUrlError)}
              aria-describedby={jobUrlError ? "job-url-error" : undefined}
              value={jobUrl}
              onChange={(event) => {
                setJobUrl(event.target.value);
                if (event.target.value.trim()) setJobUrlError("");
              }}
              placeholder="https://example.com/jobs/role"
            />
            {jobUrlError && <p id="job-url-error" role="alert">{jobUrlError}</p>}
          </div>

          <div className="field">
            <label htmlFor="resumes">Resumes</label>
            <p id="resume-help">Select one or more PDFs. Analyze Fit sends them to the backend.</p>
            <input
              id="resumes"
              type="file"
              accept=".pdf,application/pdf"
              multiple
              aria-required="true"
              aria-invalid={Boolean(fileError)}
              onChange={selectResumes}
              aria-describedby={fileError ? "resume-help resume-error" : "resume-help"}
            />
            {fileError && <p id="resume-error" role="alert">{fileError}</p>}
            {resumeFiles.length > 0 && (
              <ul>
                {resumeFiles.map((file, index) => (
                  <li key={index}>
                    <span>{file.name}</span>
                    <button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      onClick={() => {
                        setResumeFiles((previous) =>
                          previous.filter((_, fileIndex) => fileIndex !== index),
                        );
                        if (resumeFiles.length === 1) {
                          setFileError("Select at least one PDF resume.");
                        }
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="field">
            <label htmlFor="additional-notes">Additional Notes</label>
            <textarea
              id="additional-notes"
              rows={6}
              value={additionalNotes}
              onChange={(event) => setAdditionalNotes(event.target.value)}
            />
          </div>

          <button type="submit" disabled={isLoading}>
            {isLoading ? "Submitting..." : "Analyze Fit"}
          </button>
        </fieldset>
        <p role="status">{isLoading ? "Uploading files and waiting for the backend..." : ""}</p>
        {error && <p role="alert">{error}</p>}
      </form>
      {result && (
        <section aria-labelledby="debug-heading" aria-live="polite">
          <h2 id="debug-heading">Debug response</h2>
          <p>Response from the last submission. No fit analysis has been performed.</p>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
