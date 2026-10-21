import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { requestData } from "../request.mjs";

test("timeout also covers a response whose headers arrive but body never ends", async () => {
  let hits = 0;
  const sockets = new Set();
  const server = http.createServer((_request, response) => {
    hits++;
    response.writeHead(200, { "Content-Type": "application/json" });
    response.flushHeaders();
    response.write('{"unfinished":');
  });
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const start = Date.now();
    await assert.rejects(
      requestData(
        `http://127.0.0.1:${server.address().port}`,
        { method: "POST" },
        "json",
        80,
      ),
      /请求超时/,
    );
    assert.equal(hits, 1);
    assert.ok(Date.now() - start < 2000);
  } finally {
    sockets.forEach((socket) => socket.destroy());
    await new Promise((resolve) => server.close(resolve));
  }
});

test("HTTP errors preserve useful text without exposing invalid response bodies", async () => {
  const server = http.createServer((_request, response) => {
    response.writeHead(409, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ detail: "内容已更新，请刷新" }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    await assert.rejects(
      requestData(
        `http://127.0.0.1:${server.address().port}`,
        {},
        "json",
        1000,
      ),
      (error) => error.message === "内容已更新，请刷新" && error.status === 409,
    );
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
