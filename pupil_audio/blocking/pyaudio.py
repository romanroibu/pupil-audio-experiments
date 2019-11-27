import logging

import numpy as np
import pyaudio

import pupil_audio.utils.pyaudio as pyaudio_utils

from .base import Codec
from .base import InputStreamWithCodec
from .base import OutputStreamWithCodec


logger = logging.getLogger(__name__)


class PyAudioCodec(Codec[str]):

    # https://stackoverflow.com/a/22644499/1271958

    def __init__(self, frame_rate, channels: int, format:int=None, dtype:np.dtype=None):
        if format is not None and dtype is None:
            dtype = self._dtype_from_format(format)
        elif format is None and dtype is not None:
            format = self._format_from_dtype(dtype)
        else:
            raise ValueError(f"Either format or dtype should be specified, but not both")
        self.frame_rate = frame_rate
        self.format = format
        self.dtype = dtype
        self.channels = channels

    def decode(self, data: str) -> np.ndarray:
        """
        Convert a byte stream into a 2D numpy array with 
        shape (chunk_size, channels)

        Samples are interleaved, so for a stereo stream with left channel 
        of [L0, L1, L2, ...] and right channel of [R0, R1, R2, ...], the output 
        is ordered as [L0, R0, L1, R1, ...]
        """
        # TODO: handle data type as parameter, convert between pyaudio/numpy types
        result = np.fromstring(data, dtype=self.dtype)

        chunk_length = len(result) / self.channels
        assert chunk_length == int(chunk_length)

        result = np.reshape(result, (int(chunk_length), self.channels))
        return result

    def encode(self, data: np.ndarray) -> str:
        """
        Convert a 2D numpy array into a byte stream for PyAudio

        Signal should be a numpy array with shape (chunk_size, self.channels)
        """
        interleaved = data.flatten()

        # TODO: handle data type as parameter, convert between pyaudio/numpy types
        data = interleaved.astype(self.dtype).tostring()
        return data

    @staticmethod
    def _dtype_from_format(format):
        if format == pyaudio.paFloat32:
            return np.dtype('float32')
        elif format == pyaudio.paInt16:
            return np.dtype('int16')
        else:
            raise NotImplementedError()

    @staticmethod
    def _format_from_dtype(dtype):
        if dtype == np.dtype('float32'):
            return pyaudio.paFloat32
        elif dtype == np.dtype('int16'):
            return pyaudio.paInt16
        else:
            raise NotImplementedError()


class PyAudioDeviceInputStream(InputStreamWithCodec[str]):

    def __init__(self, name, channels=None, frame_rate=None, format=None, dtype=None):
        device_info = pyaudio_utils.get_input_by_name(name)
        frame_rate = frame_rate or device_info.get("defaultSampleRate", None)
        channels = channels or device_info.get("maxInputChannels", None)

        assert frame_rate is not None
        assert channels is not None

        self.name = name
        self.frame_rate = int(frame_rate)
        self.session = pyaudio_utils.create_session()
        self._codec = PyAudioCodec(
            frame_rate=frame_rate,
            channels=channels,
            format=format,
            dtype=dtype,
        )
        self.stream = self.session.open(
            format=self.format,
            channels=self.channels,
            rate=self.frame_rate,
            input=True,
            input_device_index=device_info["index"],
        )

    @property
    def codec(self) -> Codec:
        return self._codec

    def read_raw(self, chunk_size: int) -> str:
        if not self.stream.is_active:
            self.stream.start_stream()
            logger.debug("PyAudioDeviceInputStream opened")

        self.stream.frames_per_buffer = chunk_size
        return self.stream.read(chunk_size, exception_on_overflow=False)

    def close(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.debug("PyAudioDeviceInputStream closed")
        if self.session is not None:
            pyaudio_utils.destroy_session(self.session)
            self.stream = None

    @property
    def format(self) -> int:
        return self._codec.format

    @property
    def channels(self) -> int:
        return self._codec.channels

    @property
    def sample_width(self):
        with pyaudio_utils.session_context() as session:
            return session.get_sample_size(self.format)

    @staticmethod
    def enumerate_devices():
        return sorted(pyaudio_utils.get_all_inputs().values(), key=lambda x: x["index"])

    @staticmethod
    def default_device():
        return pyaudio_utils.get_default_input()


class PyAudioDeviceOutputStream(OutputStreamWithCodec[str]):

    def __init__(self):
        raise NotImplementedError  # TODO: Implement

    @staticmethod
    def enumerate_devices():
        return sorted(pyaudio_utils.get_all_outputs().values(), key=lambda x: x["index"])

    @staticmethod
    def default_device():
        return pyaudio_utils.get_default_output()
