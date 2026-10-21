"""Benchmark the real 2pass inference pipeline locally; output may contain private text."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time
import wave

from .funasr_service import Models


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('audio',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,default=Path('output/funasr/models'))
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--device',choices=('cpu','cuda:0','auto'),default='cpu')
    parser.add_argument('--runs',type=int,default=3)
    args=parser.parse_args()
    if args.runs<1:
        parser.error('--runs must be positive')
    if args.output.exists():
        parser.error('output already exists; choose another file')
    with wave.open(str(args.audio),'rb') as audio:
        if (audio.getframerate(),audio.getnchannels(),audio.getsampwidth())!=(16000,1,2):
            raise ValueError('Expected 16kHz mono PCM16 WAV')
        pcm=audio.readframes(audio.getnframes())
    import torch
    started=time.perf_counter()
    models=Models(args.model_dir,args.threads,args.device)
    cuda=models.device.startswith('cuda')
    if cuda:
        torch.cuda.synchronize()
    result={'device':models.device,'python':platform.python_version(),
            'packages':{name:importlib.metadata.version(name) for name in ('torch','torchaudio','funasr')},
            'cuda_runtime':torch.version.cuda,'threads':args.threads,
            'model_load_seconds':time.perf_counter()-started,
            'audio_sha256':hashlib.sha256(args.audio.read_bytes()).hexdigest(),
            'duration_seconds':len(pcm)/32000,
            'model_devices':{name:sorted({str(p.device) for p in item.model.parameters()})
                             for name,item in models.models.items()},'runs':[]}
    if cuda:
        result['gpu_name']=torch.cuda.get_device_name(0)
        result['gpu_capability']=list(torch.cuda.get_device_capability(0))
        result['cuda_memory_after_load']=dict(zip(('free','total'),torch.cuda.mem_get_info()))
    for index in range(args.runs):
        session=models.session()
        if cuda:
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        started=time.perf_counter()
        events=[]
        for offset in range(0,len(pcm),6400):
            events.extend(session.feed(pcm[offset:offset+6400]))
        events.extend(session.feed(b'',True))
        if cuda:
            torch.cuda.synchronize()
        elapsed=time.perf_counter()-started
        finals=[event for event in events if event['mode']=='2pass-offline']
        if not finals or not any(event.get('text','').strip() for event in finals):
            raise RuntimeError('No final recognized speech')
        run={'index':index+1,'seconds':elapsed,'real_time_factor':elapsed/result['duration_seconds'],
             'final_segments':len(finals),'events':events}
        if cuda:
            run['peak_allocated_bytes']=torch.cuda.max_memory_allocated()
            run['peak_reserved_bytes']=torch.cuda.max_memory_reserved()
            run['cuda_memory_after_run']=dict(zip(('free','total'),torch.cuda.mem_get_info()))
        result['runs'].append(run)
        print(json.dumps({k:v for k,v in run.items() if k!='events'}),flush=True)
        del session
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'BENCHMARK_SAVED {args.output}',flush=True)


if __name__=='__main__':
    main()
