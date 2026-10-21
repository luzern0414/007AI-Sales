import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import { Resampler } from "./resampler.mjs";

test("stopping sends the sub-200ms transcription tail and archives identical PCM", async () => {
  const blocks = [],
    events = [];
  let epoch, stopped;
  const done = new Promise((resolve) => {
    stopped = resolve;
  });
  const context = vm.createContext({
    Resampler,
    ArrayBuffer,
    DataView,
    Blob,
    crypto: webcrypto,
    openStore: async () => ({}),
    read: async () => epoch,
    commit: async (_db, value, block) => {
      epoch = value;
      if (block) blocks.push(block);
    },
    postMessage: (event) => {
      events.push(event);
      if (event.type === "stopped" || event.type === "error") stopped();
    },
  });
  const source = (
    await readFile(new URL("./recorder.worker.mjs", import.meta.url), "utf8")
  ).replace(/^import .*;\r?\n/gm, "");
  vm.runInContext(source, context);
  context.onmessage({
    data: {
      type: "init",
      userId: "isolated",
      sampleRate: 48000,
      epoch: { id: "tail", nextSeq: 0 },
    },
  });
  context.onmessage({
    data: {
      type: "samples",
      samples: Float32Array.from(
        { length: 4800 },
        (_, i) => Math.sin(i / 9) * 0.3,
      ),
    },
  });
  context.onmessage({ data: { type: "stop" } });
  await done;
  assert.equal(
    events.find((x) => x.type === "error"),
    undefined,
  );
  const archive = Buffer.concat(
    await Promise.all(
      blocks.map(async (x) => Buffer.from(await x.pcm.arrayBuffer())),
    ),
  );
  const sent = Buffer.concat(
    events.filter((x) => x.type === "asr").map((x) => Buffer.from(x.bytes)),
  );
  assert.ok(archive.length > 0 && archive.length < 6400);
  assert.deepEqual(sent, archive);
});
