import logging
import platform
import contextlib

import numpy as np
import av

from .base import Codec
from .base import InputStreamWithCodec
from .base import OutputStreamWithCodec


logger = logging.getLogger(__name__)


class PyAVCodec(Codec[av.AudioFrame]):
    # https://stackoverflow.com/a/22644499/1271958

    def __init__(self, channels: int, frame_rate, format:str=None, dtype:np.dtype=None):
        if format is not None and dtype is None:
            dtype = self._dtype_from_format(format)
        elif format is None and dtype is not None:
            format = self._format_from_dtype(dtype)
        else:
            raise ValueError(f"Either format or dtype should be specified, but not both")
        self.channels = channels
        self.frame_rate = frame_rate
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

        data = data.flatten(order='F')

        chunk_length = len(data) / self.channels
        assert chunk_length == int(chunk_length)

        data = np.reshape(data, (self.channels, int(chunk_length)))

        data = self._frame_from_ndarray(data, self.channels, self.format)

        data.rate = self.frame_rate

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

    # https://github.com/mikeboers/PyAV/blob/master/av/audio/frame.pyx
    _format_dtypes = {
        'dbl': '<f8',
        'dblp': '<f8',
        'flt': '<f4',
        'fltp': '<f4',
        's16': '<i2',
        's16p': '<i2',
        's32': '<i4',
        's32p': '<i4',
        'u8': 'u1',
        'u8p': 'u1',
    }

    # https://github.com/FFmpeg/FFmpeg/blob/master/libavutil/channel_layout.c
    _channel_layout_names = {
        1: "mono",
        2: "stereo",
        3: "3.0",
        4: "quad",
        5: "5.0",
        6: "hexagonal",
        7: "7.0",
        8: "octagonal",
        16: "hexadecagonal",
    }

    @staticmethod
    def _frame_from_ndarray(array, channels, format):
        """
        Construct a frame from a numpy array.
        """

        format_dtypes = PyAVCodec._format_dtypes
        nb_channels = channels
        layout = PyAVCodec._channel_layout_names[channels]

        # map avcodec type to numpy type
        try:
            dtype = np.dtype(format_dtypes[format])
        except KeyError:
            raise ValueError('Conversion from numpy array with format `%s` is not yet supported' % format)

        # nb_channels = len(av.AudioLayout(layout).channels)
        assert array.dtype == dtype
        assert array.ndim == 2
        if av.AudioFormat(format).is_planar:
            assert array.shape[0] == nb_channels, f"array.shape={array.shape}, nb_channels={nb_channels}"
            samples = array.shape[1]
        else:
            assert array.shape[0] == 1
            samples = array.shape[1] // nb_channels

        frame = av.AudioFrame(format=format, layout=layout, samples=samples)
        for i, plane in enumerate(frame.planes):
            plane.update(array[i, :])
        return frame


class PyAVFileInputStream(InputStreamWithCodec[av.AudioFrame]):

    def __init__(self):
        raise NotImplementedError  # TODO: Implement


class PyAVFileOutputStream(OutputStreamWithCodec[av.AudioFrame]):

    def __init__(self, path, channels:int, frame_rate, format:str=None, dtype:np.dtype=None):
        self.path = path
        self.frame_rate = frame_rate
        self.container = None
        self.stream = None
        self._codec = PyAVCodec(
            channels=channels,
            frame_rate=frame_rate,
            format=format,
            dtype=dtype,
        )

    @property
    def codec(self) -> Codec:
        return self._codec

    def write_raw(self, data: av.AudioFrame):
        if self.container is None:
            self.container = av.open(self.path, 'w')
            self.stream = self.container.add_stream('aac', rate=self.frame_rate)
            logger.debug(f"Opened stream: {self.path}")

        data.pts = None

        for packet in self.stream.encode(data):
            self.container.mux(packet)

    def close(self):
        if self.container is not None:
            for packet in self.stream.encode(None):
                self.container.mux(packet)
            self.container.close()
            self.container = None
            self.stream = None
            logger.debug(f"Closed stream: {self.path}")

    @property
    def format(self) -> int:
        return self._codec.format
