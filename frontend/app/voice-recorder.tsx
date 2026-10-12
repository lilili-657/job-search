"use client";

import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../lib/audio-api";

type Phase = "idle" | "requesting" | "recording" | "stopping";

export default function VoiceRecorder({ onBusyChange, onTranscript }: {
  onBusyChange: (busy: boolean) => void;
  onTranscript: (text: string) => void;
}) {
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [transcribed, setTranscribed] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const busy = useRef(false);
  const generation = useRef(0);
  const stoppedAt = useRef<number | null>(null);

  function releaseMicrophone() {
    if (timer.current !== null) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  useEffect(() => {
    return () => {
      generation.current += 1;
      const active = recorder.current;
      if (active) {
        active.ondataavailable = null;
        active.onstop = null;
        active.onerror = null;
        if (active.state !== "inactive") active.stop();
      }
      releaseMicrophone();
    };
  }, []);

  useEffect(() => {
    if (!audioBlob) {
      setAudioUrl("");
      return;
    }
    const url = URL.createObjectURL(audioBlob);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [audioBlob]);

  async function start() {
    if (busy.current) return;
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Recording is unavailable. Use a supported browser on HTTPS or localhost.");
      return;
    }
    busy.current = true;
    onBusyChange(true);
    setPhase("requesting");
    const request = ++generation.current;
    try {
      const microphone = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Permission may resolve after cancellation or navigation.
      if (request !== generation.current) {
        microphone.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = microphone;
      const active = new MediaRecorder(microphone);
      recorder.current = active;
      const chunks: Blob[] = [];
      let failed = false;
      stoppedAt.current = null;
      const startedAt = performance.now();
      active.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      active.onerror = () => {
        failed = true;
        setError("Recording failed. Please try again.");
        releaseMicrophone();
      };
      active.onstop = () => {
        releaseMicrophone();
        recorder.current = null;
        busy.current = false;
        onBusyChange(false);
        setPhase("idle");
        setSeconds(Math.floor(((stoppedAt.current ?? performance.now()) - startedAt) / 1000));
        if (!failed) {
          const blob = new Blob(chunks, { type: active.mimeType });
          if (blob.size > 0) setAudioBlob(blob);
          else setError("No audio was captured. Please try again.");
        }
      };
      active.start();
      setTranscribed(false);
      setAudioBlob(null);
      setSeconds(0);
      setPhase("recording");
      timer.current = setInterval(() => {
        setSeconds(Math.floor((performance.now() - startedAt) / 1000));
      }, 250);
    } catch (cause) {
      if (request !== generation.current) return;
      releaseMicrophone();
      recorder.current = null;
      busy.current = false;
      onBusyChange(false);
      setPhase("idle");
      setError(cause instanceof DOMException && cause.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access to record."
        : "Could not start recording. Check that a microphone is available and try again.");
    }
  }

  function stop() {
    const active = recorder.current;
    if (!active || active.state === "inactive") return;
    stoppedAt.current = performance.now();
    setPhase("stopping");
    active.stop();
    releaseMicrophone();
  }

  function cancelRequest() {
    generation.current += 1;
    busy.current = false;
    onBusyChange(false);
    setPhase("idle");
  }

  async function sendAudio() {
    if (!audioBlob || busy.current || transcribed) return;
    busy.current = true;
    setIsUploading(true);
    onBusyChange(true);
    setError("");
    setTranscribed(false);
    const request = generation.current;
    try {
      const result = await transcribeAudio(audioBlob);
      if (request === generation.current) {
        onTranscript(result.text);
        setTranscribed(true);
        setAudioBlob(null);
        setSeconds(0);
      }
    } catch (cause) {
      if (request === generation.current) {
        setError(cause instanceof Error ? cause.message : "Transcription failed. Please try again.");
      }
    } finally {
      if (request === generation.current) {
        busy.current = false;
        setIsUploading(false);
        onBusyChange(false);
      }
    }
  }

  const duration = `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;

  return (
    <section className="voice-recorder" aria-labelledby="voice-heading">
      <h2 id="voice-heading">Voice recording</h2>
      <p>Transcribe sends your recording to OpenAI and adds the text to Additional Notes. You can edit it before clicking Analyze Fit.</p>
      <p role="status">
        {phase === "recording" ? "Recording" : phase === "requesting" ? "Waiting for microphone permission…" : phase === "stopping" ? "Finishing recording…" : audioBlob ? "Recording ready" : "No recording"}
      </p>
      <p className="recording-duration">Duration: <span role="timer">{duration}</span></p>
      <div className="recording-actions">
        {phase === "idle" && <button type="button" onClick={start} disabled={isUploading}>{audioBlob ? "Re-record" : "Record"}</button>}
        {phase === "requesting" && <button type="button" onClick={cancelRequest}>Cancel</button>}
        {(phase === "recording" || phase === "stopping") && (
          <button type="button" onClick={stop} disabled={phase === "stopping"}>Stop</button>
        )}
        {audioBlob && phase === "idle" && (
          <>
            <button type="button" disabled={isUploading} onClick={sendAudio}>
              {isUploading ? "Transcribing…" : "Transcribe"}
            </button>
            <button type="button" disabled={isUploading} onClick={() => { setAudioBlob(null); setSeconds(0); setError(""); setTranscribed(false); }}>Delete recording</button>
          </>
        )}
      </div>
      {audioBlob && audioUrl && phase === "idle" && <audio controls src={audioUrl} aria-label="Recorded audio playback" />}
      <div role="status">
        {isUploading && <p>Transcribing audio…</p>}
        {transcribed && <p>Transcript added to Additional Notes. Review and edit it before analysis.</p>}
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
