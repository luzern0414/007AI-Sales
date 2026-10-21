export async function requestData(
  url,
  options = {},
  format = "json",
  timeoutMs = 30000,
) {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) abort();
  else options.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const error = new Error(
        typeof body?.detail === "string" ? body.detail : "操作失败，请重试",
      );
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return undefined;
    return format === "blob" ? await response.blob() : await response.json();
  } catch (error) {
    if (timedOut) throw new Error("请求超时，请检查结果后重试");
    if (controller.signal.aborted) throw new Error("请求已取消");
    if (error.status) throw error;
    throw new Error("连接中断，请联网后重试");
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
