import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";

test("streaming resampler preserves sample count and attenuates aliases", async () => {
  assert.ok(
    existsSync(new URL("./resampler.mjs", import.meta.url)),
    "Streaming resampler is missing",
  );
  const { Resampler } = await import("./resampler.mjs");
  function signal(frequency) {
    const r = new Resampler(48000, 16000);
    const out = [];
    for (let offset = 0; offset < 48000; offset += 128) {
      const a = Float32Array.from(
        { length: Math.min(128, 48000 - offset) },
        (_, i) => Math.sin((2 * Math.PI * frequency * (offset + i)) / 48000),
      );
      out.push(...r.push(a));
    }
    out.push(...r.finish());
    return out;
  }
  const low = signal(1000),
    high = signal(12000);
  assert.equal(low.length, 16000);
  assert.equal(high.length, 16000);
  const rms = (a) =>
    Math.sqrt(
      a.slice(200, -200).reduce((s, x) => s + x * x, 0) / (a.length - 400),
    );
  assert.ok(rms(low) > 0.65);
  assert.ok(rms(high) < 0.02, "High frequencies must not alias into speech");
});
