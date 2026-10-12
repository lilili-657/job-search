import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../lib/audio-api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { transcribeAudio, appendTranscript } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("sends Blob bytes, filename, and MIME type through FormData", async (t) => {
  for (const [mime, filename] of [["audio/webm;codecs=opus", "recording.webm"], ["audio/mp4", "recording.m4a"]]) {
    const blob = new Blob([new Uint8Array([0, 128, 255, 1])], { type: mime });
    const expected = { text: "Spoken notes." };
    const mock = t.mock.method(globalThis, "fetch", async (url, options) => {
      assert.equal(url, "http://localhost:8000/api/transcribe");
      assert.equal(options.method, "POST");
      assert.equal(options.headers, undefined);
      assert.ok(options.body instanceof FormData);
      assert.deepEqual([...options.body.keys()], ["audio"]);
      const file = options.body.get("audio");
      assert.equal(file.name, filename);
      assert.equal(file.type, mime);
      assert.deepEqual(await file.arrayBuffer(), await blob.arrayBuffer());
      return Response.json(expected);
    });
    assert.deepEqual(await transcribeAudio(blob), expected);
    mock.mock.restore();
  }
});

test("reports network, HTTP, and malformed response failures", async (t) => {
  const blob = new Blob(["audio"], { type: "audio/webm" });
  const mock = t.mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  await assert.rejects(transcribeAudio(blob), /Could not upload audio/);
  mock.mock.mockImplementation(async () => Response.json({ detail: "Upload rejected" }, { status: 422 }));
  await assert.rejects(transcribeAudio(blob), /Upload rejected/);
  mock.mock.mockImplementation(async () => Response.json({ filename: "recording.webm", mime_type: "audio/webm", byte_size: -1 }));
  await assert.rejects(transcribeAudio(blob), /No transcript was returned/);
});

test("appends editable transcript without overwriting existing notes", () => {
  assert.equal(appendTranscript("Typed notes", " Spoken notes. "), "Typed notes\nSpoken notes.");
  assert.equal(appendTranscript("", "Spoken notes."), "Spoken notes.");
  assert.equal(appendTranscript("Latest manual edit\n", "More notes"), "Latest manual edit\nMore notes");
  assert.equal(appendTranscript("Keep these notes", "  "), "Keep these notes");
});
