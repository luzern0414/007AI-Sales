"""Download fixed FunASR model artifacts from ModelScope and verify SHA-256."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

MODELS = {
    "paraformer-zh": "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "fsmn-vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "ct-punc": "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
}


def download(item, destination):
    alias, model_id = item
    root = destination.resolve() / alias
    root.mkdir(parents=True, exist_ok=True)
    api = f"https://modelscope.cn/api/v1/models/{model_id}/repo/files?Revision=v2.0.4&Recursive=true"
    with urllib.request.urlopen(api, timeout=60) as response:
        manifest = json.load(response)
    files = [f for f in manifest["Data"]["Files"] if f["Type"] == "blob" and
             "/" not in f["Path"] and f["Name"] not in {".DS_Store", ".gitattributes"}]
    for record in files:
        target = root / record["Path"]
        expected = record["Sha256"]
        if target.exists() and hashlib.file_digest(target.open("rb"), "sha256").hexdigest() == expected:
            continue
        url = f"https://modelscope.cn/models/{model_id}/resolve/v2.0.4/{urllib.parse.quote(record['Path'])}"
        print(f"DOWNLOAD {alias}/{record['Name']} ({record['Size']} bytes)", flush=True)
        partial = target.with_suffix(target.suffix + ".partial")
        if record['Size'] > 32 * 1024 * 1024:
            if not partial.exists() or partial.stat().st_size != record['Size']:
                with partial.open("wb") as handle:
                    handle.truncate(record['Size'])
            def part(start):
                end = min(start + 16 * 1024 * 1024, record['Size']) - 1
                receipt = root / f"{record['Name']}.part-{start}.sha256"
                if receipt.exists():
                    with partial.open("rb") as handle:
                        handle.seek(start)
                        previous = handle.read(end - start + 1)
                    if hashlib.sha256(previous).hexdigest() == receipt.read_text().strip():
                        return
                for attempt in range(3):
                    try:
                        request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                        with urllib.request.urlopen(request, timeout=90) as response:
                            if response.status != 206:
                                raise RuntimeError("Range request not honored")
                            content = response.read(end - start + 2)
                        if len(content) != end - start + 1:
                            raise RuntimeError("Incomplete range response")
                        with partial.open("r+b") as handle:
                            handle.seek(start)
                            handle.write(content)
                        receipt.write_text(hashlib.sha256(content).hexdigest())
                        print(f"PART {alias} {end + 1}/{record['Size']}", flush=True)
                        return
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(2 * (attempt + 1))
            with ThreadPoolExecutor(max_workers=12) as pool:
                list(pool.map(part, range(0, record['Size'], 16 * 1024 * 1024)))
        else:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
        with partial.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch: {target}")
        partial.replace(target)
        print(f"VERIFIED {alias}/{record['Name']}", flush=True)
    (root / "download-manifest.json").write_text(json.dumps({
        "model_id": model_id, "revision": "v2.0.4", "files": files,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    parser.add_argument("--streaming",action="store_true")
    args=parser.parse_args()
    if args.streaming:
        MODELS["paraformer-zh-streaming"] = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
    with ThreadPoolExecutor(max_workers=3) as pool:
        for path in pool.map(lambda item: download(item,args.destination), MODELS.items()):
            print(f"READY {path}", flush=True)
