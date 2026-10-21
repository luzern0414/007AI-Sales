export function sealedRecovery(local, remote) {
  if (!remote) throw new Error("云端录音段不存在");
  if (!remote.sealed) return false;
  if (
    remote.id !== local.id ||
    remote.next_seq !== local.nextSeq ||
    remote.contiguous_frames !== local.totalFrames ||
    remote.total_frames !== local.totalFrames
  )
    throw new Error("本机与云端录音范围不一致，请保留本机数据");
  return true;
}
