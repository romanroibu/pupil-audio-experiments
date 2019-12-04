import queue
import threading
import typing as T
from fractions import Fraction

import numpy as np
import pyaudio
import av

from pupil_audio.utils.pyaudio import DeviceInfo

from .pyaudio import PyAudioDeviceSource
from .pyav import PyAVFileSink


class PyAudio2PyAVCapture:

    @staticmethod
    def available_input_devices():
        return sorted(DeviceInfo.inputs_by_name().keys())

    def __init__(self, in_name: str, out_path: str, frame_rate=None, channels=None, dtype=None, transcoder_cls=None):
        device = DeviceInfo.named_input(in_name)

        frame_rate = int(frame_rate or device.default_sample_rate)
        channels = int(channels or device.max_input_channels)

        self.shared_queue = queue.Queue()

        transcoder_cls = transcoder_cls or PyAudio2PyAVTranscoder
        assert issubclass(transcoder_cls, PyAudio2PyAVTranscoder)

        self.transcoder = transcoder_cls(
            frame_rate=frame_rate,
            channels=channels,
            dtype=dtype,
        )

        self.source = PyAudioDeviceSource(
            device_index=device.index,
            frame_rate=self.transcoder.frame_rate,
            channels=self.transcoder.channels,
            format=self.transcoder.pyaudio_format,
            out_queue=self.shared_queue,
        )

        self.sink = PyAVFileSink(
            file_path=out_path,
            transcoder=self.transcoder,
            frame_rate=self.transcoder.frame_rate,
            channels=self.transcoder.channels,
            format=self.transcoder.pyav_format,
            in_queue=self.shared_queue,
        )

    def start(self):
        self.sink.start()
        self.source.start()

    def stop(self):
        self.sink.stop()
        self.source.stop()


class PyAudio2PyAVTranscoder():

    def __init__(self, frame_rate, channels, dtype=None):
        dtype = dtype or np.dtype("int16")
        assert dtype in self._supported_dtypes()

        self.frame_rate = frame_rate
        self.channels = channels
        self.dtype = dtype
        self.num_encoded_frames = 0

    def start(self):
        pass

    def stop(self):
        pass

    _dtype_to_pyaudio_format = {
        np.dtype("<f4"): pyaudio.paFloat32,
        np.dtype("<i2"): pyaudio.paInt16,
        np.dtype("<i4"): pyaudio.paInt32,
        np.dtype("u1"): pyaudio.paUInt8,
    }

    # https://github.com/mikeboers/PyAV/blob/master/av/audio/frame.pyx
    _dtype_to_pyav_format_interleaved_and_planar = {
        np.dtype("<f8"): ("dbl", "dblp"),
        np.dtype("<f4"): ("flt", "fltp"),
        np.dtype("<i2"): ("s16", "s16p"),
        np.dtype("<i4"): ("s32", "s32p"),
        np.dtype("u1"): ("u8", "u8p"),
    }

    # https://github.com/FFmpeg/FFmpeg/blob/master/libavutil/channel_layout.c
    _channels_to_pyav_layout = {
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

    def _supported_dtypes(self) -> T.Set[np.dtype]:
        dtypes = set()
        dtypes.update(self._dtype_to_pyaudio_format.keys())
        dtypes.update(self._dtype_to_pyav_format_interleaved_and_planar.keys())
        return dtypes

    @property
    def pyaudio_format(self) -> int:
        try:
            return self._dtype_to_pyaudio_format[self.dtype]
        except KeyError:
            raise ValueError(f"Couldn't map {self.dtype} dtype to a PyAudio format")

    @property
    def pyav_format(self) -> str:
        try:
            interleaved, planar = self._dtype_to_pyav_format_interleaved_and_planar[self.dtype]
            return planar
        except KeyError:
            raise ValueError(f"Couldn't map {self.dtype} dtype to a PyAV format")

    @property
    def pyav_layout(self) -> str:
        try:
            return self._channels_to_pyav_layout[self.channels]
        except KeyError:
            raise ValueError(f"Couldn't map {self.channels} channels to a PyAV layout")

    def transcode(self, in_frame: np.ndarray, time_info: pyaudio_utils.TimeInfo) -> T.Tuple[av.AudioFrame, float]:

        # Step 1: Decode PyAudio input frame

        tmp_frame = np.fromstring(in_frame, dtype=self.dtype)

        chunk_length = len(tmp_frame) / self.channels
        assert chunk_length == int(chunk_length)
        chunk_length = int(chunk_length)

        tmp_frame = np.reshape(tmp_frame, (chunk_length, self.channels))

        # Step 2: Encode PyAV output frame

        # Flatten in column-major (Fortran-style) order
        # Effectively converting the buffer to a planar audio frame
        tmp_frame = tmp_frame.flatten(order='F')

        chunk_length = len(tmp_frame) / self.channels
        assert chunk_length == int(chunk_length)
        chunk_length = int(chunk_length)

        tmp_frame = np.reshape(tmp_frame, (self.channels, chunk_length))

        assert tmp_frame.ndim == 2
        if av.AudioFormat(self.pyav_format).is_planar:
            assert tmp_frame.shape[0] == self.channels
            samples = tmp_frame.shape[1]
        else:
            assert tmp_frame.shape[0] == 1
            samples = tmp_frame.shape[1] // self.channels

        out_frame = av.AudioFrame(format=self.pyav_format, layout=self.pyav_layout, samples=samples)

        for i, plane in enumerate(out_frame.planes):
            plane.update(tmp_frame[i, :])

        out_frame.rate = self.frame_rate
        out_frame.time_base = Fraction(1, self.frame_rate)
        out_frame.pts = out_frame.samples * self.num_encoded_frames
        self.num_encoded_frames += 1

        return out_frame, time_info.input_buffer_adc_time
