import wave
import numpy as np

from .base import Codec
from .base import InputStreamWithCodec
from .base import OutputStreamWithCodec

from .pyaudio import PyAudioCodec


class WaveCodec(PyAudioCodec):
    pass


class WaveFileInputStream(InputStreamWithCodec[str]):

    def __init__(self):
        raise NotImplementedError  # TODO: Implement


class WaveFileOutputStream(OutputStreamWithCodec[str]):

    def __init__(self, path, channels, frame_rate, sample_width, format=None, dtype=None):
        self.path = path
        self.file = None
        self.channels = channels
        self.frame_rate = frame_rate
        self.sample_width = sample_width
        self._codec = WaveCodec(
            channels=channels,
            format=format,
            dtype=dtype,
        )

    @property
    def codec(self) -> Codec:
        return self._codec

    def write_raw(self, data: np.ndarray):
        if self.file is None:
            self.file = wave.open(self.path, "wb")
            self.file.setnchannels(self.channels)
            self.file.setframerate(self.frame_rate)
            self.file.setsampwidth(self.sample_width)
        self.file.writeframes(data)

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
