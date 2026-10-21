import pytest
from pathlib import Path
import subprocess
import sys

from scripts import transcribe_funasr


def test_batch_accepts_explicit_device_and_output_without_changing_defaults():
    parser=transcribe_funasr.build_parser()
    args=parser.parse_args(['source.wav','--work-dir','work','--device','cuda:0','--output','chosen.md'])
    assert args.device=='cuda:0'
    assert str(args.output)=='chosen.md'
    defaults=parser.parse_args(['source.wav','--work-dir','work'])
    assert defaults.device=='cpu'
    assert defaults.output is None


def test_batch_rejects_unsupported_device():
    with pytest.raises(SystemExit):
        transcribe_funasr.build_parser().parse_args(['source.wav','--work-dir','work','--device','cuda:9'])


def test_batch_direct_entrypoint_refuses_existing_output_before_loading_audio(tmp_path):
    source=tmp_path/'source.wav'
    source.write_bytes(b'not decoded because output exists')
    output=tmp_path/'chosen.md'
    output.write_text('keep me',encoding='utf-8')
    command=[sys.executable,str(Path(transcribe_funasr.__file__)),str(source),
             '--work-dir',str(tmp_path/'work'),'--output',str(output)]
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode!=0
    assert 'Transcript already exists' in run.stderr
    assert output.read_text(encoding='utf-8')=='keep me'
    assert not (tmp_path/'work').exists()
