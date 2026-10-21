import {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  type ReactNode,
} from "react";
import { api, post } from "../api";
// @ts-expect-error Browser storage module is shared with the module worker.
import { openStore, read, commit, allEpochs, writeNote } from "./local.mjs";
// @ts-expect-error Recovery validation is shared with Node contract tests.
import { sealedRecovery } from "./recovery.mjs";
// @ts-expect-error Shared transport lifecycle has Node regression tests.
import { Transcription } from "./transcription.mjs";

export interface Meeting {
  id: string;
  project_id: string | null;
  project_ids?: string[];
  projects?: { id: string; name: string }[];
  analysis_status?: string;
  ai_summary?: string;
  title: string;
  notes: string;
  transcript: string;
  status: string;
  version: number;
  created_at: string;
  occurred_at?: string | null;
  recordings?: { file_id: string; name: string; mime: string; active?: boolean; transcript?: string; summary?: string }[];
}
interface Epoch {
  id: string;
  token: string;
  meetingId: string;
  title: string;
  nextSeq: number;
  totalFrames: number;
  cloudSeq: number;
  stopped?: boolean;
  sealed?: boolean;
  interruption?: { kind: InterruptionKind; detected_at: string };
}
type InterruptionKind =
  | "input_stalled"
  | "device_ended"
  | "device_muted"
  | "context_suspended"
  | "overflow"
  | "storage_failed"
  | "recovered";
interface RecordingState {
  active: boolean;
  busy: boolean;
  meetingId: string | null;
  localFrames: number;
  cloudFrames: number;
  error: string;
  recoveries: Epoch[];
  start: (m: Meeting) => Promise<void>;
  stop: (reason?: InterruptionKind) => Promise<void>;
  recover: (e: Epoch) => Promise<void>;
  refresh: () => Promise<void>;
  asrStatus: string;
  partial: string;
  liveText: string;
  saveDraft: (id: string, note: unknown) => Promise<void>;
  loadDraft: (id: string) => Promise<any>;
  clearDraft: (
    id: string,
    expected?: { notes: string; transcript: string },
  ) => Promise<void>;
}
const Context = createContext<RecordingState>(null!);
export const useRecording = () => useContext(Context);
export function RecordingProvider({
  userId,
  children,
}: {
  userId: string;
  children: ReactNode;
}) {
  const [active, setActive] = useState(false),
    [busy, setBusy] = useState(false),
    [meetingId, setMeetingId] = useState<string | null>(null),
    [localFrames, setLocal] = useState(0),
    [cloudFrames, setCloud] = useState(0),
    [error, setError] = useState(""),
    [recoveries, setRecoveries] = useState<Epoch[]>([]);
  const [asrStatus, setAsrStatus] = useState("转写未连接"),
    [partial, setPartial] = useState(""),
    [liveText, setLiveText] = useState("");
  const resources = useRef<{
    worker: Worker;
    context: AudioContext;
    stream: MediaStream;
    node: AudioWorkletNode;
    epoch: Epoch;
    release?: () => void;
    watchdog?: ReturnType<typeof setInterval>;
    detach?: () => void;
    lastSample: number;
  } | null>(null);
  const starting = useRef(false),
    stopping = useRef<Promise<void> | null>(null);
  const dbRef = useRef<IDBDatabase | null>(null),
    transcriptionRef = useRef<InstanceType<typeof Transcription> | null>(null),
    uploading = useRef<Promise<void> | null>(null),
    current = useRef<Epoch | null>(null),
    stopResolve = useRef<(() => void) | null>(null);
  async function database() {
    return dbRef.current ?? (dbRef.current = await openStore(userId));
  }
  async function refresh() {
    const db = await database();
    const epochs: Epoch[] = await allEpochs(db);
    setRecoveries(
      epochs.filter(
        (e) =>
          !e.sealed && (e.id !== current.current?.id || !resources.current),
      ),
    );
  }
  async function sync(e: Epoch, wait = false): Promise<void> {
    if (uploading.current) {
      if (!wait) return;
      await uploading.current;
      return sync(e, true);
    }
    if (!navigator.onLine) return;
    const operation = syncCapture(e);
    uploading.current = operation;
    try {
      await operation;
    } finally {
      if (uploading.current === operation) uploading.current = null;
    }
  }
  async function syncCapture(e: Epoch) {
    try {
      const db = await database();
      let stored: Epoch = await read(db, "epochs", e.id);
      const manifest = await api("/meetings/" + e.meetingId + "/manifest");
      const remote = manifest.epochs.find((x: { id: string }) => x.id === e.id);
      if (sealedRecovery(stored, remote)) {
        await commit(db, { ...stored, sealed: true, stopped: true });
        setCloud(stored.totalFrames);
        if (current.current?.id === e.id) current.current = null;
        await refresh();
        setError("");
        return;
      }
      let next = remote?.next_seq ?? 0;
      let frames = remote?.contiguous_frames ?? 0;
      while (next < stored.nextSeq) {
        const b = await read(db, "blocks", e.id + ":" + next);
        if (!b) throw new Error("本机录音块缺失");
        const response = await api("/epochs/" + e.id + "/blocks/" + next, {
          method: "PUT",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Audio-Hash": b.hash,
            "X-Frame-Start": String(b.frameStart),
            "X-Capture-Token": e.token,
          },
          body: b.pcm,
        });
        next = response.next_seq;
        frames = response.contiguous_frames;
        stored = await read(db, "epochs", e.id);
        setCloud(frames);
      }
      stored = await read(db, "epochs", e.id);
      if (stored.stopped) {
        if (stored.interruption)
          await post("/epochs/" + e.id + "/interruption", {
            token: e.token,
            ...stored.interruption,
          });
        await post("/epochs/" + e.id + "/seal", {
          token: e.token,
          last_seq: stored.nextSeq - 1,
          total_frames: stored.totalFrames,
        });
        await commit(db, { ...stored, sealed: true });
        if (current.current?.id === e.id) current.current = null;
        await refresh();
      }
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }
  function openTranscription(mid: string) {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(
      scheme + "//" + location.host + "/api/meetings/" + mid + "/transcribe",
    );
    transcriptionRef.current?.close();
    transcriptionRef.current = new Transcription(socket, setAsrStatus,
      (value: {text: string; final: boolean}) => {
          if (value.final) {
            setLiveText((text) => text + value.text + "\n");
            setPartial("");
          } else setPartial(value.text);
      });
  }
  async function start(m: Meeting) {
    if (resources.current || starting.current || stopping.current || busy)
      throw new Error("已有录音正在进行");
    starting.current = true;
    setBusy(true);
    setError("");
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    let release: (() => void) | undefined;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
        throw new Error("请使用HTTPS或本机地址录音");
      if (!navigator.locks) throw new Error("当前浏览器不支持安全录音");
      let decide: (value: boolean) => void = () => {};
      const acquired = new Promise<boolean>((r) => (decide = r));
      navigator.locks.request(
        "sales-microphone",
        { ifAvailable: true },
        async (lock) => {
          decide(!!lock);
          if (lock) await new Promise<void>((r) => (release = r));
        },
      );
      if (!(await acquired)) throw new Error("另一页面正在录音");
      const storage = await navigator.storage.estimate();
      if (
        storage.quota &&
        storage.usage &&
        storage.quota - storage.usage < 256 * 1024 * 1024
      )
        throw new Error("本机可用空间不足256MB");
      await navigator.storage.persist().catch(() => false);
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      context = new AudioContext();
      await context.audioWorklet.addModule("/audio-capture.js");
      await context.resume();
      const created = await post("/meetings/" + m.id + "/epochs", {});
      const epoch: Epoch = {
        ...created,
        meetingId: m.id,
        title: m.title,
        nextSeq: 0,
        totalFrames: 0,
        cloudSeq: -1,
      };
      const worker = new Worker(
        new URL("./recorder.worker.mjs", import.meta.url),
        { type: "module" },
      );
      const node = new AudioWorkletNode(context, "meeting-capture");
      const ready = new Promise<void>((resolve, reject) => {
        worker.onmessage = (event) => {
          const msg = event.data;
          if (msg.type === "ready") resolve();
          if (msg.type === "asr") {
            transcriptionRef.current?.push(msg.bytes);
          }
          if (msg.type === "ack") node.port.postMessage("ack");
          if (msg.type === "saved") {
            setLocal(msg.totalFrames);
            sync(epoch);
          }
          if (msg.type === "stopped") {
            stopResolve.current?.();
            stopResolve.current = null;
          }
          if (msg.type === "error") {
            setError(msg.message);
            if (resources.current) stop("storage_failed").catch(() => {});
            else stream?.getTracks().forEach((t) => t.stop());
            reject(new Error(msg.message));
          }
        };
      });
      worker.postMessage({
        type: "init",
        epoch,
        userId,
        sampleRate: context.sampleRate,
      });
      await ready;
      resources.current = {
        worker,
        node,
        context,
        stream,
        epoch,
        release,
        lastSample: performance.now(),
      };
      current.current = epoch;
      setMeetingId(m.id);
      setLocal(0);
      setCloud(0);
      setPartial("");
      setLiveText("");
      openTranscription(m.id);
      node.port.onmessage = (event) => {
        if (event.data.type === "samples") {
          if (resources.current)
            resources.current.lastSample = performance.now();
          worker.postMessage({ type: "samples", samples: event.data.samples }, [
            event.data.samples.buffer,
          ]);
        }
        if (event.data.type === "stopped") worker.postMessage({ type: "stop" });
        if (event.data.type === "gap") {
          setError("录音输入中断");
          stop("overflow").catch(() => {});
        }
      };
      const source = context.createMediaStreamSource(stream);
      source.connect(node);
      const gain = context.createGain();
      gain.gain.value = 0;
      node.connect(gain);
      gain.connect(context.destination);
      stream.getTracks().forEach((track) =>
        track.addEventListener("ended", () => {
          setError("麦克风已断开");
          stop("device_ended").catch(() => {});
        }),
      );
      // Switching pages or briefly backgrounding the tab must not end a meeting:
      // transient mutes and suspensions get a grace period and a resume attempt.
      stream.getTracks().forEach((track) =>
        track.addEventListener("mute", () => {
          setTimeout(() => {
            if (resources.current && track.muted) {
              setError("麦克风不可用，录音已暂停");
              stop("device_muted").catch(() => {});
            }
          }, 3000);
        }),
      );
      const suspended = () =>
        context!.state === "suspended" ||
        String(context!.state) === "interrupted";
      context.addEventListener("statechange", () => {
        if (!resources.current || !suspended()) return;
        context!.resume().catch(() => {});
        setTimeout(() => {
          if (resources.current && suspended()) {
            setError("录音被系统暂停");
            stop("context_suspended").catch(() => {});
          }
        }, 4000);
      });
      let wake: { release: () => Promise<void> } | null = null;
      const keepAwake = () => {
        const lock = (navigator as Navigator & {
          wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> };
        }).wakeLock;
        lock?.request("screen").then((w) => (wake = w)).catch(() => {});
      };
      const visible = () => {
        if (document.visibilityState !== "visible" || !resources.current) return;
        resources.current.lastSample = performance.now();
        if (suspended()) context!.resume().catch(() => {});
        keepAwake();
      };
      document.addEventListener("visibilitychange", visible);
      keepAwake();
      resources.current.detach = () => {
        document.removeEventListener("visibilitychange", visible);
        wake?.release().catch(() => {});
      };
      resources.current.watchdog = setInterval(() => {
        const state = resources.current;
        // Hidden tabs throttle timers and message delivery; only judge stalls while visible.
        if (document.visibilityState !== "visible") return;
        if (state && performance.now() - state.lastSample > 6000) {
          setError("录音输入中断，已暂停");
          stop("input_stalled").catch(() => {});
        }
      }, 1000);
      setActive(true);
    } catch (err) {
      stream?.getTracks().forEach((t) => t.stop());
      await context?.close();
      release?.();
      setError((err as Error).message);
      throw err;
    } finally {
      starting.current = false;
      setBusy(false);
    }
  }
  async function stop(reason?: InterruptionKind) {
    if (stopping.current) return stopping.current;
    const operation = stopCapture(reason);
    stopping.current = operation;
    try {
      await operation;
    } finally {
      stopping.current = null;
    }
  }
  async function stopCapture(reason?: InterruptionKind) {
    const r = resources.current;
    if (!r) return;
    setBusy(true);
    setActive(false);
    clearInterval(r.watchdog);
    r.detach?.();
    const detectedAt = new Date().toISOString();
    async function retainInterruption() {
      if (!reason) return;
      const db = await database();
      const stored = await read(db, "epochs", r!.epoch.id);
      if (stored)
        await commit(db, {
          ...stored,
          interruption: { kind: reason, detected_at: detectedAt },
        });
    }
    try {
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(
          () => reject(new Error("录音尾部未确认，请恢复已保存内容")),
          10000,
        );
        stopResolve.current = () => {
          clearTimeout(timer);
          resolve();
        };
        r.node.port.postMessage("stop");
      });
      await retainInterruption();
      r.stream.getTracks().forEach((t) => t.stop());
      const transcriptionDone = transcriptionRef.current?.stop();
      await r.context.close();
      r.worker.terminate();
      r.release?.();
      resources.current = null;
      await sync(r.epoch, true);
      await refresh();
      await transcriptionDone;
    } catch (err) {
      await retainInterruption().catch(() => {});
      setError((err as Error).message);
      r.stream.getTracks().forEach((t) => t.stop());
      await r.context.close().catch(() => {});
      r.worker.terminate();
      r.release?.();
      transcriptionRef.current?.close();
      resources.current = null;
      current.current = null;
      await refresh();
      throw err;
    } finally {
      setBusy(false);
    }
  }
  async function recover(e: Epoch) {
    setBusy(true);
    setError("");
    try {
      const db = await database();
      const manifest = await api("/meetings/" + e.meetingId + "/manifest");
      const remote = manifest.epochs.find((x: { id: string }) => x.id === e.id);
      if (sealedRecovery(e, remote)) {
        await commit(db, { ...e, sealed: true, stopped: true });
        setMeetingId(e.meetingId);
        setLocal(e.totalFrames);
        setCloud(e.totalFrames);
        await refresh();
        return;
      }
      const result = await post("/epochs/" + e.id + "/restore", {
        last_seq: e.nextSeq - 1,
        total_frames: e.totalFrames,
      });
      const restored = {
        ...e,
        token: result.token,
        stopped: true,
        interruption:
          e.interruption ||
          (!e.stopped
            ? {
                kind: "recovered" as const,
                detected_at: new Date().toISOString(),
              }
            : undefined),
      };
      await commit(db, restored);
      setMeetingId(e.meetingId);
      setLocal(e.totalFrames);
      await sync(restored);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const retry = () => {
      if (current.current) sync(current.current);
      else refresh().catch(() => {});
    };
    window.addEventListener("online", retry);
    const timer = setInterval(retry, 5000);
    const leave = (event: BeforeUnloadEvent) => {
      if (resources.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", leave);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", retry);
      window.removeEventListener("beforeunload", leave);
      const r = resources.current;
      clearInterval(r?.watchdog);
      r?.detach?.();
      r?.stream.getTracks().forEach((t) => t.stop());
      r?.context.close();
      r?.worker.terminate();
      r?.release?.();
      transcriptionRef.current?.close();
      dbRef.current?.close();
      dbRef.current = null;
    };
  }, [userId]);
  return (
    <Context.Provider
      value={{
        active,
        busy,
        meetingId,
        localFrames,
        cloudFrames,
        error,
        recoveries,
        start,
        stop,
        recover,
        refresh,
        asrStatus,
        partial,
        liveText,
        saveDraft: async (id, note) => {
          await writeNote(await database(), id, note);
        },
        loadDraft: async (id) => read(await database(), "notes", id),
        clearDraft: async (id, expected) => {
          await writeNote(await database(), id, null, expected);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function duration(frames: number) {
  const seconds = Math.floor(frames / 16000);
  return (
    Math.floor(seconds / 60)
      .toString()
      .padStart(2, "0") +
    ":" +
    (seconds % 60).toString().padStart(2, "0")
  );
}
