import { Resampler } from "./resampler.mjs";
import { openStore, commit, read } from "./local.mjs";
let db,
  resampler,
  epoch,
  buffer = [],
  seq = 0,
  frameStart = 0,
  chain = Promise.resolve(),
  queued = 0,
  failed = false,
  asrBuffer = [];
function notify(type, extra = {}) {
  postMessage({ type, ...extra });
}
function emitAsr(final = false) {
  while (asrBuffer.length >= 3200 || (final && asrBuffer.length)) {
    const size = Math.min(3200, asrBuffer.length),
      bytes = new ArrayBuffer(size * 2),
      view = new DataView(bytes);
    for (let i = 0; i < size; i++)
      view.setInt16(
        i * 2,
        Math.round(
          Math.max(-1, Math.min(1, asrBuffer[i])) *
            (asrBuffer[i] < 0 ? 32768 : 32767),
        ),
        true,
      );
    asrBuffer.splice(0, size);
    postMessage({ type: "asr", bytes }, [bytes]);
  }
}
async function persist(final = false) {
  while (buffer.length >= 16000 || (final && buffer.length)) {
    const size = Math.min(16000, buffer.length),
      bytes = new ArrayBuffer(size * 2),
      view = new DataView(bytes);
    for (let i = 0; i < size; i++)
      view.setInt16(
        i * 2,
        Math.round(
          Math.max(-1, Math.min(1, buffer[i])) *
            (buffer[i] < 0 ? 32768 : 32767),
        ),
        true,
      );
    buffer.splice(0, size);
    const hash = [
      ...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    ]
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
    const latest = await read(db, "epochs", epoch.id);
    epoch = {
      ...epoch,
      cloudSeq: latest?.cloudSeq ?? -1,
      nextSeq: seq + 1,
      totalFrames: frameStart + size,
    };
    await commit(db, epoch, {
      key: epoch.id + ":" + seq,
      epoch: epoch.id,
      seq,
      frameStart,
      frames: size,
      hash,
      pcm: new Blob([bytes], { type: "application/octet-stream" }),
    });
    seq++;
    frameStart += size;
    notify("saved", { epoch: epoch.id, totalFrames: frameStart, nextSeq: seq });
  }
}
onmessage = (event) => {
  const message = event.data;
  if (message.type === "samples") queued++;
  if (queued > 64) {
    failed = true;
    notify("error", { message: "录音处理繁忙，已停止采集" });
    return;
  }
  chain = chain
    .then(async () => {
      if (failed) return;
      if (message.type === "init") {
        db = await openStore(message.userId);
        epoch = message.epoch;
        resampler = new Resampler(message.sampleRate);
        await commit(db, epoch);
        notify("ready");
      }
      if (message.type === "samples") {
        const values = resampler.push(message.samples);
        buffer.push(...values);
        asrBuffer.push(...values);
        emitAsr();
        await persist();
        queued--;
        notify("ack");
      }
      if (message.type === "stop") {
        const tail = resampler.finish();
        buffer.push(...tail);
        asrBuffer.push(...tail);
        emitAsr(true);
        await persist(true);
        epoch = { ...epoch, stopped: true };
        await commit(db, epoch);
        notify("stopped", { epoch });
      }
    })
    .catch((error) => {
      failed = true;
      notify("error", { message: error.message || "本机保存失败" });
    });
};
