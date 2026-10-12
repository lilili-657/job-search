export type TranscriptionResponse = {
  text: string;
};

export async function transcribeAudio(blob: Blob): Promise<TranscriptionResponse> {
  const extensions: Record<string, string> = {
    "audio/webm": "webm", "video/webm": "webm",
    "audio/mp4": "m4a", "video/mp4": "mp4",
    "audio/ogg": "ogg", "audio/wav": "wav", "audio/mpeg": "mp3",
  };
  const mediaType = blob.type.split(";")[0].trim().toLowerCase();
  const filename = `recording.${extensions[mediaType] ?? "bin"}`;
  const formData = new FormData();
  formData.append("audio", blob, filename);

  let response: Response;
  try {
    response = await fetch("http://localhost:8000/api/transcribe", {
      method: "POST",
      // Let the browser set Content-Type and the multipart boundary.
      body: formData,
    });
  } catch {
    throw new Error("Could not upload audio. Check that the backend is running and try again.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(typeof data?.detail === "string"
      ? data.detail : `Transcription failed (${response.status}). Please try again.`);
  }
  if (!data || typeof data.text !== "string" || !data.text.trim()) {
    throw new Error("No transcript was returned. Please try a new recording.");
  }
  return data;
}

export function appendTranscript(notes: string, transcript: string): string {
  const text = transcript.trim();
  if (!text) return notes;
  return notes ? `${notes}${notes.endsWith("\n") ? "" : "\n"}${text}` : text;
}
