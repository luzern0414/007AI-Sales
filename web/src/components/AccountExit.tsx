import { useEffect, useRef, useState } from "react";
import { LogOut } from "lucide-react";
import { post } from "../api";
import { useRecording } from "../recording/runtime";
// @ts-expect-error Sequence is shared with Node regression tests.
import { exitSession } from "../recording/exit.mjs";

export default function AccountExit({ onExit }: { onExit: () => void }) {
  const recording = useRecording();
  const latest = useRef(recording);
  latest.current = recording;
  const onExitRef = useRef(onExit);
  onExitRef.current = onExit;
  const leaving = useRef(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const expired = async () => {
      if (leaving.current) return;
      leaving.current = true;
      setBusy(true);
      try {
        await latest.current.stop();
      } catch {
        /* Saved blocks remain available on this device after login. */
      }
      onExitRef.current();
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  async function logout() {
    if (leaving.current || recording.busy) return;
    leaving.current = true;
    setBusy(true);
    setError("");
    try {
      await exitSession(recording.stop, () => post("/auth/logout", {}), onExit);
    } catch (e) {
      setError((e as Error).message);
      leaving.current = false;
      setBusy(false);
    }
  }
  return (
    <div className="account-exit">
      <button
        className="icon-button"
        aria-label="退出登录"
        disabled={busy || recording.busy}
        onClick={logout}
      >
        <LogOut size={18} />
      </button>
      {error && (
        <span className="account-exit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
