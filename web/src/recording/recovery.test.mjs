import test from "node:test";
import assert from "node:assert/strict";
import { sealedRecovery } from "./recovery.mjs";

test("a cloud seal is accepted only for the exact local recording", () => {
  const local = { id: "e", nextSeq: 3, totalFrames: 42000 };
  assert.equal(sealedRecovery(local, { id: "e", sealed: false }), false);
  assert.equal(
    sealedRecovery(local, {
      id: "e",
      sealed: true,
      next_seq: 3,
      contiguous_frames: 42000,
      total_frames: 42000,
    }),
    true,
  );
  assert.throws(
    () =>
      sealedRecovery(local, {
        id: "e",
        sealed: true,
        next_seq: 2,
        contiguous_frames: 32000,
        total_frames: 32000,
      }),
    /不一致/,
  );
  assert.throws(() => sealedRecovery(local, undefined), /不存在/);
});
