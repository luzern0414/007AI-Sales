"""Explicit shared device policy for local batch and streaming ASR."""


def resolve_device(requested, torch_module=None):
    if requested not in ('cpu', 'cuda:0', 'auto'):
        raise ValueError('device must be cpu, cuda:0 or auto')
    if requested == 'cpu':
        return 'cpu'
    if torch_module is None:
        import torch as torch_module
    available = torch_module.cuda.is_available()
    if requested == 'auto':
        return 'cuda:0' if available else 'cpu'
    if not available:
        raise RuntimeError('CUDA unavailable. Install the GPU environment or restart with CPU: --device cpu')
    return requested
