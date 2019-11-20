import platform
import contextlib

import numpy as np
import pyaudio as pa

from .base import Codec
from .base import InputStreamWithCodec
from .base import OutputStreamWithCodec


# TODO: Move to a shared location
AUDIO_INPUT_NO_AUDIO_NAME = "No Audio"
AUDIO_INPUT_DEFAULT_NAME = "Default"


class PyAudioCodec(Codec[str]):
    # https://stackoverflow.com/a/22644499/1271958

    def __init__(self, channels: int, format:int=None, dtype:np.dtype=None):
        if format is not None and dtype is None:
            dtype = self._dtype_from_format(format)
        elif format is None and dtype is not None:
            format = self._format_from_dtype(dtype)
        else:
            raise ValueError(f"Either format or dtype should be specified, but not both")
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
        if format == pa.paFloat32:
            return np.dtype('float32')
        elif format == pa.paInt16:
            return np.dtype('int16')
        else:
            raise NotImplementedError()

    @staticmethod
    def _format_from_dtype(dtype):
        if dtype == np.dtype('float32'):
            return pa.paFloat32
        elif dtype == np.dtype('int16'):
            return pa.paInt16
        else:
            raise NotImplementedError()


class PyAudioDeviceInputStream(InputStreamWithCodec[str]):

    def __init__(self, name, channels, frame_rate, format=None, dtype=None, session=None):
        self.name = name
        self.format = format
        self.channels = channels
        self.frame_rate = frame_rate
        self.session = session
        self.stream = None
        self._codec = PyAudioCodec(
            channels=channels,
            format=format,
            dtype=dtype,
        )

    @property
    def codec(self) -> Codec:
        return self._codec

    def read_raw(self, chunk_size: int) -> str:
        if self.session is None:
            self.session = _create_pyaudio_session()
        if self.stream is None:
            device_info = _pyaudio_input_info(self.name)
            self.stream = self.session.open(
                format=self.format,
                channels=self.channels,
                rate=self.frame_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=chunk_size,
            )
            self.stream.start_stream()
        return self.stream.read(chunk_size, exception_on_overflow=False)

    def close(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if self.session is not None:
            _destroy_pyaudio_session(self.session)
            self.stream = None

    @property
    def sample_width(self):
        with _pyaudio_session_context() as session:
            return session.get_sample_size(self.format)


class PyAudioDeviceOutputStream(OutputStreamWithCodec[str]):

    def __init__(self):
        raise NotImplementedError  # TODO: Implement


# PRIVATE


def _pyaudio_input_info(name: str):
    input_devices = _pyaudio_inputs()
    try:
        device_info = input_devices[name]
    except KeyError:
        available_devices = ", ".join(sorted(input_devices.keys()))
        raise ValueError(f"No device named \"{name}\". Available devices: {available_devices}.")
    return device_info


def _pyaudio_inputs():
    return {k: v for k, v in _pyaudio_devices().items() if v.get("maxInputChannels", 0) > 0}


def _pyaudio_outputs():
    return {k: v for k, v in _pyaudio_devices().items() if v.get("maxOutputChannels", 0) > 0}


def _pyaudio_devices():
    if platform.system() == "Linux":
        return _linux_pyaudio_devices()
    elif platform.system() == "Darwin":
        return _macos_pyaudio_devices()
    elif platform.system() == "Windows":
        return _windows_pyaudio_devices()
    else:
        raise NotImplementedError("Unsupported operating system")


def _linux_pyaudio_devices():
    devices = {
        AUDIO_INPUT_NO_AUDIO_NAME: {
            "name": AUDIO_INPUT_NO_AUDIO_NAME,
            "index": pa.paNoDevice,
        },
    }

    for device_info in _pyaudio_devices_by_api(pa.paALSA):
        # print(device_info)

        if "default" == device_info["name"]:
            devices[AUDIO_INPUT_DEFAULT_NAME] = device_info

        if "hw:" in device_info["name"]:
            devices[device_info["name"]] = device_info

    return devices


def _macos_pyaudio_devices():
    devices = {
        AUDIO_INPUT_NO_AUDIO_NAME: {
            "name": AUDIO_INPUT_NO_AUDIO_NAME,
            "index": pa.paNoDevice,
        },
    }

    for device_index, device_info in enumerate(_pyaudio_devices_by_api(pa.paCoreAudio)):
        # print(device_info)
        device_info["index"] = device_index

        # TODO: Check if default device

        if "NoMachine" not in device_info["name"]:
            devices[device_info["name"]] = device_info

    return devices


def _windows_pyaudio_devices():
    devices = {
        AUDIO_INPUT_NO_AUDIO_NAME: {
            "name": AUDIO_INPUT_NO_AUDIO_NAME,
            "index": None, # TODO: Why is this None instead of pyaudio.paNoDevice?
        },
    }

    for device_info in _pyaudio_devices_by_api(pa.paDirectSound):
        # print(device_info)

        # TODO: Check if default device

        devices[device_info["name"]] = device_info

    return devices


def _pyaudio_devices_by_api(api):

    with _pyaudio_session_context() as session:

        host_api_info = session.get_host_api_info_by_type(api)

        host_api_index = host_api_info["index"]
        device_count = host_api_info["deviceCount"]

        for device_index in range(device_count):
            device_info = session.get_device_info_by_host_api_device_index(host_api_index, device_index)
            yield device_info


@contextlib.contextmanager
def _pyaudio_session_context():
    try:
        session = _create_pyaudio_session()
        yield session
    finally:
        _destroy_pyaudio_session(session)


def _create_pyaudio_session():
    # TODO: Send stdout to /dev/null while initializing the session
    session = pa.PyAudio()
    return session


def _destroy_pyaudio_session(session):
    session.terminate()


if __name__ == "__main__":
    print(f"Inputs:")
    for name, info in _pyaudio_inputs().items():
        print(f"\t{name}")
        print(f"\t\t{info}")
    print(f"------------------------------------------")
    print(f"Outputs:")
    for name, info in _pyaudio_outputs().items():
        print(f"\t{name}")
        print(f"\t\t{info}")
