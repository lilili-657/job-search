import os
from pathlib import PurePath
from typing import Annotated

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.transcription import TranscriptionResponse

router = APIRouter(prefix="/api")
MAX_AUDIO_BYTES = 25_000_000
AUDIO_EXTENSIONS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(audio: Annotated[UploadFile, File()]) -> TranscriptionResponse:
    """Transcribe one upload; close its temporary stream on success or failure."""
    try:
        if not audio.filename or PurePath(audio.filename).suffix.lower() not in AUDIO_EXTENSIONS:
            raise HTTPException(422, "Choose a supported audio file such as WebM, M4A, MP3, or WAV.")
        size = 0
        while chunk := audio.file.read(64 * 1024):
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                raise HTTPException(413, "Audio must be 25 MB or smaller.")
        if size == 0:
            raise HTTPException(422, "The audio file is empty.")
        audio.file.seek(0)

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(503, "Transcription is not configured on the server.")
        try:
            with requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": "gpt-transcribe", "response_format": "json"},
                files={"file": (audio.filename, audio.file, audio.content_type or "application/octet-stream")},
                timeout=(10, 90),
            ) as response:
                if response.status_code == 429:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = {}
                    error = payload.get("error", {}) if isinstance(payload, dict) else {}
                    error = error if isinstance(error, dict) else {}
                    messages = {
                        "credit_balance_exhausted": "OpenAI API credits are exhausted. Check API billing and credit balance before retrying.",
                        "organization_spend_limit_exceeded": "OpenAI organization spend limit reached. Check organization limits before retrying.",
                        "project_spend_limit_exceeded": "OpenAI project spend limit reached. Check this project's limits before retrying.",
                        "organization_usage_limit_exceeded": "OpenAI organization usage limit reached. Check approved usage limits before retrying.",
                        "insufficient_quota": "OpenAI API quota is unavailable. Check API billing, credits, and usage limits before retrying.",
                        "rate_limit_exceeded": "Transcription is temporarily rate limited. Wait before retrying.",
                        "slow_down": "OpenAI requests are arriving too quickly. Wait before retrying.",
                    }
                    code = error.get("code")
                    message = messages.get(code) if isinstance(code, str) else None
                    if not message and error.get("type") == "insufficient_quota":
                        message = messages["insufficient_quota"]
                    if not message and error.get("type") == "rate_limit_error":
                        message = messages["rate_limit_exceeded"]
                    raise HTTPException(429, message or "OpenAI returned 429. Check API billing and usage limits; the response did not identify a specific cause.")
                if response.status_code in (400, 413, 415, 422):
                    raise HTTPException(422, "The audio could not be transcribed. Try a new recording or supported audio file.")
                if response.status_code == 401:
                    raise HTTPException(503, "OpenAI rejected server authentication (401). Check OPENAI_API_KEY, project permissions, and IP restrictions, then restart the backend.")
                if response.status_code == 403:
                    raise HTTPException(503, "OpenAI denied access (403). Check project permissions and any organization or region restrictions.")
                if not response.ok:
                    raise HTTPException(502, "The transcription service is unavailable. Try again later.")
                try:
                    result = response.json()
                except ValueError as exc:
                    raise HTTPException(502, "The transcription service returned an invalid response.") from exc
        except requests.Timeout as exc:
            raise HTTPException(504, "Transcription timed out. Please try again.") from exc
        except requests.RequestException as exc:
            raise HTTPException(502, "Could not reach the transcription service. Please try again.") from exc

        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise HTTPException(502, "The transcription service returned an invalid response.")
        text = result["text"].strip()
        if not text:
            raise HTTPException(422, "No speech was transcribed. Please try a new recording.")
        return TranscriptionResponse(text=text)
    finally:
        # No permanent audio files, database records, or application-level cache.
        audio.file.close()
