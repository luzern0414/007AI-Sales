"""Opt-in real-model regression, using generated silence and no private recording."""
import os
from pathlib import Path

import pytest

from scripts.funasr_service import Inference


@pytest.mark.skipif(not os.getenv('FUNASR_MODEL_DIR'),reason='Requires downloaded local model')
def test_real_vad_retains_bounded_state_through_a_minute_of_silence():
    import torch
    from funasr import AutoModel
    torch.set_num_threads(4)
    model=AutoModel(model=str(Path(os.environ['FUNASR_MODEL_DIR'])/'fsmn-vad'),device='cpu',
                    disable_update=True,disable_pbar=True,ncpu=4,max_single_segment_time=20000)
    inference=Inference({'fsmn-vad':model})
    maximum=0
    for _ in range(300):
        assert inference.vad(bytes(6400),False)==[]
        stats=inference.vad_cache['stats']
        maximum=max(maximum,len(stats.data_buf_all))
    assert maximum<400000, f'SDK retained {maximum} waveform samples during silence'
    assert inference.vad(b'',True)==[]


@pytest.mark.skipif(not os.getenv('FUNASR_MODEL_DIR'),reason='Requires downloaded local model')
def test_rotation_after_unaligned_endpoint_does_not_repeat_sdk_input():
    import torch
    from funasr import AutoModel
    torch.set_num_threads(4)
    model=AutoModel(model=str(Path(os.environ['FUNASR_MODEL_DIR'])/'fsmn-vad'),device='cpu',
                    disable_update=True,disable_pbar=True,ncpu=4,max_single_segment_time=20000)
    inference=Inference({'fsmn-vad':model})
    for _ in range(50):
        inference.vad(bytes(6400),False)
    # A confirmed endpoint may land between transport frame boundaries.
    inference.vad_last_end=9250*32
    inference.vad(bytes(6400),False)
    assert inference.vad_origin==9250*32
    assert inference.vad_cache['stats'].frm_cnt<=95
    # The browser also emits a sub-200ms tail before its separate stop message.
    inference.vad(bytes(800),False)
    assert len(inference.vad_cache['prev_samples'])==0
    assert inference.vad(b'',True)==[]
