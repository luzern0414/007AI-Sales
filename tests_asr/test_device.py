from types import SimpleNamespace

import pytest

from scripts import funasr_service


def runtime(available):
    return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: available))


def test_explicit_cuda_never_silently_falls_back_to_cpu():
    with pytest.raises(RuntimeError, match='CUDA.*CPU'):
        funasr_service.resolve_device('cuda:0', runtime(False))


def test_auto_selects_available_device_and_cpu_is_explicit():
    assert funasr_service.resolve_device('auto', runtime(True)) == 'cuda:0'
    assert funasr_service.resolve_device('auto', runtime(False)) == 'cpu'
    assert funasr_service.resolve_device('cpu', runtime(True)) == 'cpu'


def test_invalid_device_is_rejected():
    with pytest.raises(ValueError):
        funasr_service.resolve_device('cuda:99', runtime(True))
