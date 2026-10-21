"""Local file transcription. Run with the isolated .venv-asr interpreter."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time
import wave


def stamp(milliseconds):
    seconds = int(milliseconds / 1000)
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda:0", "auto"), default="cpu")
    parser.add_argument("--output", type=Path)
    return parser


def main():
    args = build_parser().parse_args()
    source = args.audio.resolve(strict=True)
    output = (args.output.resolve() if args.output else
              source.with_name(source.stem + "-FunASR转写稿.md"))
    if output.exists():
        raise FileExistsError(f"Transcript already exists: {output}")
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MODELSCOPE_CACHE", str(work.parent / "models"))
    import imageio_ffmpeg
    wav = work / "audio-16k.wav"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-i", str(source),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
    with wave.open(str(wav), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    print(f"AUDIO_DURATION_SECONDS={duration:.3f}", flush=True)
    import torch
    # Support both `python scripts/transcribe_funasr.py` and module invocation.
    if __package__:
        from .funasr_device import resolve_device
    else:
        from funasr_device import resolve_device
    device = resolve_device(args.device, torch)
    torch.set_num_threads(args.threads)
    from funasr import AutoModel
    load_start = time.monotonic()
    def model_path(alias):
        return str((args.model_dir / alias).resolve()) if args.model_dir else alias
    model = AutoModel(model=model_path("paraformer-zh"), model_revision="v2.0.4",
                      vad_model=model_path("fsmn-vad"), vad_model_revision="v2.0.4",
                      punc_model=model_path("ct-punc"), punc_model_revision="v2.0.4",
                      device=device, ncpu=args.threads, disable_update=True,
                      vad_kwargs={"max_single_segment_time": 30000})
    if str(next(model.model.parameters()).device) != device:
        raise RuntimeError(f"Requested {device}, actual {next(model.model.parameters()).device}")
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    load_seconds = time.monotonic() - load_start
    print(f"MODEL_LOAD_SECONDS={load_seconds:.3f}", flush=True)
    started = time.monotonic()
    result = model.generate(input=str(wav), batch_size_s=60, sentence_timestamp=True)
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    metadata = {
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "duration_seconds": duration, "device": device, "threads": args.threads,
        "model_load_seconds": load_seconds, "inference_seconds": elapsed,
        "real_time_factor": elapsed / duration,
        "packages": {name: importlib.metadata.version(name) for name in
                     ["funasr", "torch", "torchaudio", "modelscope", "imageio-ffmpeg"]},
        "model": "paraformer-zh", "vad_model": "fsmn-vad", "punc_model": "ct-punc",
        "model_revision": "v2.0.4", "result": result,
    }
    (work / "result.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2,
                                                 default=lambda x: x.tolist()), encoding="utf-8")
    sentences = result[0].get("sentence_info", [])
    if not sentences or not result[0].get("text", "").strip():
        raise RuntimeError("No timestamped speech returned; inspect result.json")
    lines = [f"# {source.stem}｜FunASR 转写稿", "", f"- 录音：{source.name}",
             f"- 时长：{stamp(duration * 1000)}", f"- 引擎：FunASR / Paraformer-zh（本地 {device}）",
             "- 识别稿未经逐句听校；时间以解码后的音频为准，未做说话人识别。", ""]
    for item in sentences:
        lines.extend([f"**[{stamp(item['start'])}–{stamp(item['end'])}]** {item['text'].strip()}", ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(json.dumps({"transcript": str(output), "sentences": len(sentences),
                      "inference_seconds": elapsed, "duration_seconds": duration}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
