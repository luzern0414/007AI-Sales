import test from "node:test";
import assert from "node:assert/strict";
import { exitSession } from "./exit.mjs";

test("logout waits for the recording tail before revoking the session", async () => {
  const calls = [];
  let release;
  const tail = new Promise((resolve) => {
    release = resolve;
  });
  const operation = exitSession(
    async () => {
      calls.push("flush");
      await tail;
      calls.push("saved");
    },
    async () => {
      calls.push("logout");
    },
    () => {
      calls.push("unmount");
    },
  );
  await Promise.resolve();
  assert.deepEqual(calls, ["flush"]);
  release();
  await operation;
  assert.deepEqual(calls, ["flush", "saved", "logout", "unmount"]);
});

test("failed tail save or logout keeps the authenticated app mounted", async () => {
  const calls = [];
  await assert.rejects(
    exitSession(
      async () => {
        throw new Error("tail failed");
      },
      async () => {
        calls.push("logout");
      },
      () => {
        calls.push("unmount");
      },
    ),
    /tail failed/,
  );
  assert.deepEqual(calls, []);
  await assert.rejects(
    exitSession(
      async () => {},
      async () => {
        throw new Error("offline");
      },
      () => {
        calls.push("unmount");
      },
    ),
    /offline/,
  );
  assert.deepEqual(calls, []);
});
