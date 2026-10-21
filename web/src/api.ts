import { useEffect, useState, useCallback } from "react";
// @ts-expect-error Transport is exercised against a real HTTP server in Node tests.
import { requestData } from "./request.mjs";

function requestTimeout(url: string, options: RequestInit) {
  if (/\/sync$/.test(url)) return 150000;
  if (/\/(generate|ask)$/.test(url) || options.body instanceof FormData)
    return 120000;
  return 30000;
}
function notifyExpired(error: Error & { status?: number }, url: string): never {
  if (error.status === 401 && !url.startsWith("/auth/"))
    window.dispatchEvent(new Event("session-expired"));
  throw error;
}

export async function api<T = any>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const isForm = options.body instanceof FormData;
  try {
    return await requestData(
      "/api" + url,
      {
        ...options,
        headers: {
          ...(!isForm && options.body
            ? { "Content-Type": "application/json" }
            : {}),
          ...options.headers,
        },
      },
      "json",
      requestTimeout(url, options),
    );
  } catch (error) {
    return notifyExpired(error as Error & { status?: number }, url);
  }
}
export const post = <T = any>(url: string, body: unknown) =>
  api<T>(url, { method: "POST", body: JSON.stringify(body) });
export const patch = <T = any>(url: string, body: unknown) =>
  api<T>(url, { method: "PATCH", body: JSON.stringify(body) });
export function useResource<T>(path: string, interval = 0) {
  const [value, setValue] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    if (!interval) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, interval);
    const online = () => refresh();
    window.addEventListener("online", online);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", online);
    };
  }, [interval, refresh]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<T>(path)
      .then((v) => {
        if (active) setValue(v);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return { value, error, loading, refresh };
}
export function navigate(path: string) {
  window.location.hash = path;
}
export async function download(url: string, name: string) {
  let blob: Blob;
  try {
    blob = await requestData("/api" + url, {}, "blob", 120000);
  } catch (error) {
    return notifyExpired(error as Error & { status?: number }, url);
  }
  const href = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = href;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(href), 10000);
}

/** POST and read a server-sent event stream; resolves when the server closes it. */
export async function stream(url: string, body: unknown, onEvent: (event: string, data: any) => void, signal?: AbortSignal) {
  let response: Response;
  try {
    response = await fetch("/api" + url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify(body), signal });
  } catch {
    if (signal?.aborted) throw new Error("已停止");
    throw new Error("连接中断，请联网后重试");
  }
  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null);
    const error = Object.assign(new Error(typeof detail?.detail === "string" ? detail.detail : "操作失败，请重试"), { status: response.status });
    return notifyExpired(error, url);
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
        let event = "message", data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) onEvent(event, JSON.parse(data));
      }
    }
  } catch {
    if (signal?.aborted) throw new Error("已停止");
    throw new Error("连接中断，请重试");
  }
}
