"""Bounded per-connection PCM segmentation for the private recognition service."""


class RecognitionSession:
    def __init__(self, inference):
        self.inference = inference
        self.audio = bytearray()
        self.pending = bytearray()
        self.total = 0
        self.origin = 0
        self.start = None
        self.last_end = 0
        self.closed = False

    @property
    def retained_bytes(self):
        return len(self.audio)

    def feed(self, pcm, final=False):
        if self.closed or len(pcm) > 6400 or len(pcm) % 2 or (not pcm and not final):
            raise ValueError('invalid audio input')
        self.total += len(pcm)
        self.audio.extend(pcm)
        self.pending.extend(pcm)
        events = []
        boundaries = self.inference.vad(pcm, final)
        for begin, end in boundaries:
            if begin >= 0 and (end < 0 or end > begin):
                self.start = max(int(begin * 32), self.last_end)
                if self.start < self.origin:
                    raise ValueError('VAD segment start outside retained audio')
            if end > 0:
                self._finish(min(int(end * 32), self.total), events)
        if final:
            if self.start is not None:
                self._finish(self.total, events)
            # Empty input still flushes a streaming cache created by full chunks.
            self.inference.streaming(bytes(self.pending), True)
            self.pending.clear()
            self.closed = True
        else:
            while len(self.pending) >= 19200:
                text = self.inference.streaming(bytes(self.pending[:19200]), False)
                del self.pending[:19200]
                if text:
                    events.append({'mode': '2pass-online', 'text': text, 'is_final': False})
        if self.start is not None and self.total - self.start > 22 * 32000:
            raise ValueError('speech segment duration exceeded')
        keep_from = self.start if self.start is not None else max(self.last_end, self.total - 32000)
        drop = max(0, keep_from - self.origin)
        del self.audio[:drop]
        self.origin += drop
        return events

    def _finish(self, end, events):
        if self.start is None or end <= self.start or end <= self.last_end:
            return
        if end - self.start > 22 * 32000:
            raise ValueError('speech segment duration exceeded')
        self.inference.streaming(bytes(self.pending), True)
        self.pending.clear()
        pcm = bytes(self.audio[self.start - self.origin:end - self.origin])
        text = self.inference.offline(pcm)
        if text:
            events.append({'mode': '2pass-offline', 'text': text, 'is_final': False,
                           'timestamp': [[self.start // 32, end // 32]]})
        self.inference.reset_stream()
        self.last_end = end
        self.start = None
