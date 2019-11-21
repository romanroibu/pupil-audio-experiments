import platform
import contextlib

import numpy as np
import av

from .base import Codec
from .base import InputStreamWithCodec
from .base import OutputStreamWithCodec


class PyAVCodec(Codec[av.AudioFrame]):
    # https://stackoverflow.com/a/22644499/1271958

    def __init__(self, channels: int, format:str=None, dtype:np.dtype=None):
        if format is not None and dtype is None:
            dtype = self._dtype_from_format(format)
        elif format is None and dtype is not None:
            format = self._format_from_dtype(dtype)
        else:
            raise ValueError(f"Either format or dtype should be specified, but not both")
        self.channels = channels
        self.format = format
        self.dtype = dtype

    def decode(self, data: av.AudioFrame) -> np.ndarray:
        raise NotImplementedError

    def encode(self, data: np.ndarray) -> av.AudioFrame:

        # https://docs.mikeboers.com/pyav/6.2.0/api/audio.html#module-av.audio.stream
        # https://github.com/mikeboers/PyAV/blob/develop/examples/numpy/generate_video.py
        # https://github.com/mikeboers/PyAV/blob/v6.2.0/av/audio/frame.pyx#L104
        # https://stackoverflow.com/questions/55374251/pyav-saving-video-and-audio-to-separate-files-from-streaming-hls
        # https://github.com/bastibe/SoundFile/blob/master/soundfile.py
        # https://github.com/spatialaudio/python-sounddevice/blob/master/examples/rec_unlimited.py

        chunk_length = len(data) / self.channels
        assert chunk_length == int(chunk_length)

        data = np.reshape(data, (int(chunk_length), self.channels))



        data = av.AudioFrame.from_ndarray(data, self.format)
        return data

    @staticmethod
    def _dtype_from_format(format):
        if format == "s16p":
            return np.dtype('int16')
        else:
            raise NotImplementedError()

    @staticmethod
    def _format_from_dtype(dtype):
        if dtype == np.dtype('int16'):
            return 's16p'
        else:
            raise NotImplementedError()


class PyAVFileInputStream(InputStreamWithCodec[av.AudioFrame]):

    def __init__(self):
        raise NotImplementedError  # TODO: Implement


class PyAVFileOutputStream(OutputStreamWithCodec[av.AudioFrame]):

    def __init__(self, path, channels:int, format:str=None, dtype:np.dtype=None):
        self.path = path
        self.container = None
        self.stream = None
        self._codec = PyAVCodec(
            channels=channels,
            format=format,
            dtype=dtype,
        )

    @property
    def codec(self) -> Codec:
        return self._codec

    def write_raw(self, data: av.AudioFrame):
        if self.container is None:
            self.container = av.open(self.path, 'w')
            self.stream = self.container.add_stream('mp3')  # TODO: Pass as property

        data.pts = None

        for packet in self.stream.encode(data):
            self.container.mux(packet)

        for packet in self.stream.encode(None):
            self.container.mux(packet)

    def close(self):
        if self.container is not None:
            self.container.close()
            self.container = None
            self.stream = None

    @property
    def format(self) -> int:
        return self._codec.format
