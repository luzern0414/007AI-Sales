"""Segmentation and end-of-input checks; fake inference is explicit and isolated."""
import pytest

from scripts.funasr_session import RecognitionSession


class Inference:
    def __init__(self, boundaries):
        self.boundaries = iter(boundaries)
        self.stream_audio = []
        self.offline_audio = []
        self.resets = 0

    def vad(self, pcm, final):
        return next(self.boundaries, [])

    def streaming(self, pcm, final):
        self.stream_audio.append((pcm, final))
        return '临时文字' if pcm else ''

    def offline(self, pcm):
        self.offline_audio.append(pcm)
        return '修正结果。'

    def reset_stream(self):
        self.resets += 1


def test_short_tail_is_flushed_and_completed_after_offline_correction():
    inference = Inference([[[0, -1]], [[-1, 250]]])
    session = RecognitionSession(inference)
    audio = b'\x01\x00' * 4000
    assert session.feed(audio[:6400]) == []
    events = session.feed(audio[6400:], final=True)
    assert b''.join(p for p, _ in inference.stream_audio) == audio
    assert inference.stream_audio[-1][1] is True
    assert inference.offline_audio == [audio]
    assert [e['mode'] for e in events] == ['2pass-offline']
    assert events[0]['text'] == '修正结果。'
    assert events[0]['timestamp'] == [[0, 250]]
    assert inference.resets == 1
    with pytest.raises(ValueError):
        session.feed(b'\0\0')


def test_completed_utterance_is_not_repeated_when_stopping_in_silence():
    inference = Inference([[[0, -1]], [[-1, 400]], [], []])
    session = RecognitionSession(inference)
    audio = b'\x01\x00' * 6400
    session.feed(audio[:6400])
    session.feed(audio[6400:])
    session.feed(b'\0\0' * 3200)
    assert session.feed(b'', final=True) == []
    assert inference.offline_audio == [audio]


def test_long_silence_is_bounded_and_bad_input_is_rejected():
    session = RecognitionSession(Inference([]))
    for _ in range(400):
        session.feed(b'\0\0' * 3200)
        assert session.retained_bytes <= 32000
    with pytest.raises(ValueError):
        session.feed(b'1')
    with pytest.raises(ValueError):
        session.feed(bytes(6402))


def test_missing_vad_end_fails_explicitly_before_memory_grows_unbounded():
    session = RecognitionSession(Inference([[[0, -1]]]))
    with pytest.raises(ValueError, match='segment'):
        for _ in range(130):
            session.feed(bytes(6400))


def test_inference_failure_does_not_produce_a_successful_result():
    inference = Inference([[[0, -1]], [[-1, 400]]])
    def fail(pcm):
        raise RuntimeError('inference failed')
    inference.offline = fail
    session = RecognitionSession(inference)
    session.feed(bytes(6400))
    with pytest.raises(RuntimeError, match='inference failed'):
        session.feed(bytes(6400), final=True)
