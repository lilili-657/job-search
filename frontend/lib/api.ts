export type AnalyzeDebugResponse = {
  job_url: string;
  resume_count: number;
  resume_names: string[];
  notes_length: number;
};

export async function analyzeFit(
  jobUrl: string,
  resumeFiles: File[],
  additionalNotes: string,
): Promise<AnalyzeDebugResponse> {
  const formData = new FormData();
  formData.append("job_url", jobUrl);
  formData.append("additional_notes", additionalNotes);
  for (const file of resumeFiles) {
    formData.append("resumes", file);
  }

  let response: Response;
  try {
    response = await fetch("http://localhost:8000/api/analyze", {
      method: "POST",
      // The browser supplies Content-Type, including the multipart boundary.
      body: formData,
    });
  } catch {
    throw new Error("Could not reach the backend. Check that it is running on port 8000.");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // FastAPI uses a string for HTTPException and a list for validation errors.
    const detail = data?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg}`).join("; ")
        : `Request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }

  if (
    !data ||
    typeof data.job_url !== "string" ||
    typeof data.resume_count !== "number" ||
    !Array.isArray(data.resume_names) ||
    !data.resume_names.every((name: unknown) => typeof name === "string") ||
    typeof data.notes_length !== "number"
  ) {
    throw new Error("The backend returned an unexpected response.");
  }

  return data;
}
