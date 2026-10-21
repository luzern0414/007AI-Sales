import { useEffect, useRef, useState } from "react";
import { Mic, Square, ChevronRight, LoaderCircle } from "lucide-react";
import { navigate, post } from "../api";
import { useRecording, duration, type Meeting } from "../recording/runtime";

/** Recording lives above routing: the dock keeps capture visible and stoppable on every page. */
export default function RecordDock({ home }: { home: boolean }) {
  const r = useRecording();
  const [starting, setStarting] = useState(false),
    [finishing, setFinishing] = useState(false),
    [notice, setNotice] = useState(""),
    [failure, setFailure] = useState("");
  const startingRef = useRef(false);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(t);
  }, [notice]);
  async function start() {
    if (startingRef.current || r.active) return;
    startingRef.current = true;
    setStarting(true);
    setFailure("");
    let meeting: Meeting | null = null;
    try {
      meeting = await post<Meeting>("/meetings/start", {});
      await r.start(meeting);
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      startingRef.current = false;
      setStarting(false);
    }
  }
  async function stop() {
    const id = r.meetingId;
    setFinishing(true);
    setFailure("");
    try {
      await r.stop();
      // Sealing waits for the last blocks to upload; finishing hands the meeting to the AI.
      for (let attempt = 0; id && attempt < 20; attempt++) {
        try {
          await post("/meetings/" + id + "/finish", {});
          setNotice("已保存 · AI 整理中");
          return;
        } catch (e) {
          if (!/待保存/.test((e as Error).message)) throw e;
          await new Promise((ok) => setTimeout(ok, 1500));
        }
      }
      setNotice("已存本机 · 联网后补传");
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setFinishing(false);
    }
  }
  const message = failure || (r.active ? "" : r.error);
  if (r.active)
    return (
      <div className="record-dock live" role="region" aria-label="录音中">
        <button
          className="dock-main"
          onClick={() => r.meetingId && navigate("home/" + r.meetingId)}
          aria-label="查看实时记录"
        >
          <span className="pulse" aria-hidden />
          <span className="dock-text">
            <strong>
              录音中 <time>{duration(r.localFrames)}</time>
            </strong>
            <span>{r.partial || r.liveText || r.asrStatus || "…"}</span>
          </span>
          <ChevronRight size={16} />
        </button>
        <button className="dock-stop" onClick={stop} disabled={finishing || r.busy} aria-label="停止录音">
          {finishing ? <LoaderCircle className="spin" size={16} /> : <Square size={14} fill="currentColor" />}
          停止
        </button>
      </div>
    );
  if (!home) return notice ? <div className="dock-toast" role="status">{notice}</div> : null;
  return (
    <div className="record-dock idle">
      {(notice || message) && (
        <div className={message ? "dock-toast error-toast" : "dock-toast"} role={message ? "alert" : "status"}>
          {message ? friendly(message) : notice}
        </div>
      )}
      <button className="dock-start" onClick={start} disabled={starting || r.busy}>
        <span className="mic-orb">{starting ? <LoaderCircle className="spin" size={20} /> : <Mic size={20} />}</span>
        <span>
          <strong>{starting ? "正在开始…" : "开始录音"}</strong>
        </span>
      </button>
    </div>
  );
}
function friendly(message: string) {
  if (/permission|notallowed/i.test(message)) return "请允许使用麦克风，然后重试";
  if (/notfound|device not found/i.test(message)) return "未找到麦克风，请连接后重试";
  return message;
}
