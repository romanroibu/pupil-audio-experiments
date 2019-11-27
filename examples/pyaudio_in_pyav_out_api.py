
def key_property(key: str, **kwargs):
    is_readonly = kwargs.get("readonly", False)
    assert isinstance(is_readonly, bool)

    use_default = "default" in kwargs
    default = kwargs.get("default", None)

    should_typecheck = "type" in kwargs
    klass = kwargs.get("type", None)

    def fget(self):
        try:
            return self[key]
        except KeyError:
            if use_default:
                return default
            else:
                raise

    def fset(self, value):
        if should_typecheck and not isinstance(value, klass):
            raise TypeError(f"Expected value of type \"{klass}\", but got value of type \"{type(value)}\"")
        self[key] = value

    if is_readonly:
        return property(fget=fget)
    else:
        return property(fget=fget, fset=fset, fdel=None)


class TimeInfo(dict):
    current_time = key_property("current_time", type=float, readonly=True)
    input_buffer_adc_time = key_property("input_buffer_adc_time", type=float, readonly=True)
    output_buffer_dac_time = key_property("output_buffer_dac_time", type=float, readonly=True)


class DeviceInfo(dict):
    name = key_property("name", type=str, readonly=True)
    index = key_property("index", type=int, readonly=True)
    host_api_index = key_property("hostApi", type=int, readonly=True)

    max_input_channels = key_property("maxInputChannels", type=int, readonly=True)
    max_output_channels = key_property("maxOutputChannels", type=int, readonly=True)

    default_sample_rate = key_property("defaultSampleRate", type=float, readonly=True)

    default_low_input_latency = key_property("defaultLowInputLatency", type=float, readonly=True)
    default_low_oOutput_latency = key_property("defaultLowOutputLatency", type=float, readonly=True)

    default_high_input_latency = key_property("defaultHighInputLatency", type=float, readonly=True)
    default_high_oOutput_latency = key_property("defaultHighOutputLatency", type=float, readonly=True)

    structVersion = key_property("structVersion", type=int, readonly=True)


import queue
import threading
import typing as T
from fractions import Fraction

import numpy as np
import pyaudio
import av




class PyAudioDeviceSource():

    def __init__(self, device_index, frame_rate, channels, format, out_queue):
        self._device_index = device_index
        self._frame_rate = int(frame_rate)
        self._channels = channels
        self._format = format
        self._queue = out_queue
        self._session = None
        self._stream = None

    def is_runnning(self) -> bool:
        return self._stream is not None and self._stream.is_active()

    def start(self):
        if self._session is None:
            self._session = pyaudio.PyAudio()
        if self._stream is None:
            self._stream = self._session.open(
                channels=self._channels,
                format=self._format,
                rate=self._frame_rate,
                input=True,
                input_device_index=self._device_index,
                stream_callback=self._stream_callback,
            )
        self._stream.start_stream()
        # while input_stream.is_active():
        #     time.sleep(0.1)

    def stop(self):
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._session is not None:
            self._session.terminate()
            self._session = None

    def _stream_callback(self, in_data, frame_count, time_info, status):
        time_info = TimeInfo(time_info)

        # print(f"FRAME_COUNT: {frame_count}")
        # print(f"TIME_INFO: {time_info}")
        # print(f"TIME_INFO.current_time: {time_info.current_time}")
        # print(f"TIME_INFO.input_buffer_adc_time: {time_info.input_buffer_adc_time}")
        # print(f"TIME_INFO.output_buffer_dac_time: {time_info.output_buffer_dac_time}")
        # print(f"STATUS: {status}")
        # print("-" * 80)

        timestamp = time_info.input_buffer_adc_time
        # timestamp = time_info.current_time

        try:
            self._queue.put_nowait((in_data, timestamp))
        except queue.Full:
            print(f"!!!!!!!!!!!!!!!!!!!!!! FRAME DROPPED")
            # TODO: Log warning about the queue being full
            pass

        return (None, pyaudio.paContinue)


class PyAudio2PyAV():

    def __init__(self, frame_rate, channels, dtype=np.dtype("int16"), in_queue=queue.Queue(), out_queue=queue.Queue()):
        assert dtype in self._supported_dtypes()

        self._frame_rate = frame_rate
        self._channels = channels
        self._dtype = dtype
        self._in_queue = in_queue
        self._out_queue = out_queue
        self._thread = None
        self._is_running = threading.Event()

    @property
    def frame_rate(self) -> int:
        return self._frame_rate

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def dtype(self) -> np.dtype:
        return self._dtype

    @property
    def in_queue(self):
        return self._in_queue

    @property
    def out_queue(self):
        return self._in_queue
        # return self._out_queue

    # @property
    # def is_running(self) -> bool:
    #     return self._is_running.is_set()

    # def start(self):
    #     # TODO: Clear queues
    #     self._is_running.set()
    #     self._thread = threading.Thread(
    #         name=type(self).__name__,
    #         target=self._transcode_loop,
    #         args=(),
    #     )
    #     self._thread.start()

    # def stop(self):
    #     self._is_running.clear()
    #     self._thread.join()
    #     self._thread = None
    #     # TODO: Clear queues

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
            interleaved, plannar = self._dtype_to_pyav_format_interleaved_and_planar[self.dtype]
            return plannar
        except KeyError:
            raise ValueError(f"Couldn't map {self.dtype} dtype to a PyAV format")

    @property
    def pyav_layout(self) -> str:
        try:
            return self._channels_to_pyav_layout[self._channels]
        except KeyError:
            raise ValueError(f"Couldn't map {self._channels} channels to a PyAV layout")

    def transcode(self, in_frame: np.ndarray, timestamp: float) -> T.Tuple[av.AudioFrame, float]:

        # Step 1: Decode PyAudio input frame

        tmp_frame = np.fromstring(in_frame, dtype=self.dtype)

        chunk_length = len(tmp_frame) / self.channels
        assert chunk_length == int(chunk_length)
        chunk_length = int(chunk_length)

        tmp_frame = np.reshape(tmp_frame, (chunk_length, self.channels))

        # Step 2: Encode PyAV output frame

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

        return out_frame, timestamp

    def _transcode_loop(self):
        while True:
            try:
                in_data = self.in_queue.get_nowait()
            except queue.Empty:
                if self.is_running:
                    continue
                else:
                    break

            out_data = self.transcode(*in_data)
            
            try:
                self.out_queue.put_nowait(out_data)
            except queue.Full:
                print(f"!!!!!!!!!!!!!!!!!!!!!! FRAME DROPPED")
                # TODO: Warn about dropped frame
                pass


class PyAVFileSink():
    def __init__(self, file_path, transcoder, frame_rate, channels, format, in_queue):
        self._file_path = file_path
        self._transcoder = transcoder
        self._frame_rate = frame_rate
        self._channels = channels
        self._format = format
        self._queue = in_queue
        self._thread = None
        self._running = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self):
        if self.is_running:
            return
        self._running.set()
        self._thread = threading.Thread(
            name=type(self).__name__,
            target=self._record_loop,
            args=(self._file_path, self._frame_rate),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        if not self.is_running:
            return
        self._running.clear()
        self._thread.join()
        self._thread = None

    def _record_loop(self, file_path, frame_rate):
        container = av.open(file_path, 'w')
        stream = container.add_stream('aac', rate=float(frame_rate))
        stream.time_base = Fraction(1, self._frame_rate)

        last_pts = float("-inf")
        time_base = Fraction(1, self._frame_rate)
        time_start = None

        print(f"===> FRAME_RATE: {frame_rate}")
        print(f"===> SELF._FRAME_RATE: {self._frame_rate}")
        print(f"===> STREAM TIME BASE: {stream.time_base}")

        while True:
            try:
                in_frame, in_timestamp = self._queue.get_nowait()
            except queue.Empty:
                if self.is_running:
                    continue
                else:
                    break

            out_frame, out_timestamp = self._transcoder.transcode(in_frame, in_timestamp)

            # print(f"-> PTS: {pts}")
            print(f"--> FRAME TIME BASE: {out_frame.time_base}")

            out_frame.pts = None
            # out_frame.pts = pts

            for packet in stream.encode(out_frame):
                if time_start is None:
                    time_start = out_timestamp
                    pts = 0
                else:
                    pts = int((out_timestamp - time_start) / time_base)
                    # pts = max(pts, last_pts+1)
                last_pts = pts

                # packet.pts = pts
                print(f"--> PACKET TIME BASE: {packet.time_base}")
                print(f"--> PACKET PTS: {packet.pts}")
                container.mux(packet)

        for packet in stream.encode(None):
            container.mux(packet)

        container.close()


class AudioCapture:

    @staticmethod
    def available_input_devices():
        return list(map(lambda info: DeviceInfo(info).name, _pyaudio_inputs().values()))

    @staticmethod
    def from_input_device(in_name: str, out_path: str):
        info = _pyaudio_input_info(in_name)
        info = DeviceInfo(info)
        print(info)
        return AudioCapture(
            frame_rate=int(info.default_sample_rate),
            channels=info.max_input_channels,
            input_device_index=info.index,
            output_file_path=out_path,
        )

    def __init__(self, frame_rate, channels, input_device_index, output_file_path):
        self.transcoder = PyAudio2PyAV(
            frame_rate=frame_rate,
            channels=channels,
        )
        self.source = PyAudioDeviceSource(
            device_index=input_device_index,
            frame_rate=self.transcoder.frame_rate,
            channels=self.transcoder.channels,
            format=self.transcoder.pyaudio_format,
            out_queue=self.transcoder.in_queue,
        )
        self.sink = PyAVFileSink(
            file_path=output_file_path,
            transcoder=self.transcoder,
            frame_rate=self.transcoder.frame_rate,
            channels=self.transcoder.channels,
            format=self.transcoder.pyav_format,
            in_queue=self.transcoder.out_queue,
        )

    def start(self):
        self.sink.start()
        # self.transcoder.start()
        self.source.start()

    def stop(self):
        self.sink.stop()
        # self.transcoder.stop()
        self.source.stop()





def test_async_pyaudio_api(in_name: str, out_path: str):
    info = _pyaudio_input_info(in_name)
    info = DeviceInfo(info)
    print(info)

    frame_rate = info.default_sample_rate
    channels = info.max_input_channels
    input_device_index = info.index
    output_file_path = out_path

    chunk_size = 1024 #// 2 // 2 // 2 // 2

    from _pupil_audio import pyaudio as pupil_audio_pyaudio
    from _pupil_audio import pyav as pupil_audio_pyav
    decoder = pupil_audio_pyaudio.PyAudioCodec(
        frame_rate=frame_rate,
        channels=channels,
        dtype=np.dtype("int16"),
    )
    encoder = pupil_audio_pyav.PyAVCodec(
        frame_rate=frame_rate,
        channels=channels,
        dtype=np.dtype("int16"),
    )

    shared_queue = queue.Queue()

    # source = PyAudioDeviceSource(
    #     device_index=input_device_index,
    #     frame_rate=decoder.frame_rate,
    #     channels=decoder.channels,
    #     format=decoder.format,
    #     out_queue=shared_queue,
    # )

    # sink = PyAVFileSink(
    #     file_path=output_file_path,
    #     transcoder=self.transcoder,
    #     frame_rate=self.transcoder.frame_rate,
    #     channels=self.transcoder.channels,
    #     format=self.transcoder.pyav_format,
    #     in_queue=self.transcoder.out_queue,
    # )

    input_ = pupil_audio_pyaudio.PyAudioDeviceInputStream(
        name=in_name,
        channels=decoder.channels,
        frame_rate=decoder.frame_rate,
        format=decoder.format,
    )

    output_ = pupil_audio_pyav.PyAVFileOutputStream(
        path=output_file_path,
        channels=encoder.channels,
        frame_rate=encoder.frame_rate,
        format=encoder.format,
    )

    should_run_flag = threading.Event()

    def _run_input(shared_queue, should_run_flag):
        while True:

            in_frame = input_.read_raw(chunk_size)
            out_frame = decoder.decode(in_frame)
            timestamp = 0

            try:
                shared_queue.put_nowait((out_frame, timestamp))
            except queue.Full:
                pass

            if should_run_flag.is_set():
                continue
            else:
                break

    def _run_output(shared_queue, should_run_flag):
        while True:
            try:
                in_frame, timestamp = shared_queue.get_nowait()
            except queue.Empty:
                if should_run_flag.is_set():
                    continue
                else:
                    break

            out_frame = encoder.encode(in_frame)
            output_.write_raw(out_frame)

    input_thread = threading.Thread(
        target=_run_input,
        args=(shared_queue, should_run_flag),
        daemon=True,
    )

    output_thread = threading.Thread(
        target=_run_output,
        args=(shared_queue, should_run_flag),
        daemon=True,
    )

    # source.start()
    should_run_flag.set()

    input_thread.start()
    output_thread.start()

    import time

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        # source.stop()

        should_run_flag.clear()

        input_thread.join()
        input_.close()

        output_thread.join()
        output_.close()




# PRIVATE

import logging
import platform
import contextlib
import pyaudio as pa

AUDIO_INPUT_NO_AUDIO_NAME = "No Audio"

logger = logging.getLogger(__name__)

_PYAUDIO_NO_DEVICE_INFO = {
    "name": AUDIO_INPUT_NO_AUDIO_NAME,
    "index": pa.paNoDevice,
}


def _pyaudio_default_input():
    with _pyaudio_session_context() as session:
        try:
            return session.get_default_input_device_info()
        except IOError:
            return _PYAUDIO_NO_DEVICE_INFO


def _pyaudio_default_output():
    with _pyaudio_session_context() as session:
        try:
            return session.get_default_output_device_info()
        except IOError:
            return _PYAUDIO_NO_DEVICE_INFO


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
    devices = {_PYAUDIO_NO_DEVICE_INFO["name"]: _PYAUDIO_NO_DEVICE_INFO}

    for device_info in _pyaudio_devices_by_api(pa.paALSA):
        # print(device_info)

        if "hw:" in device_info["name"] or "default" == device_info["name"]:
            devices[device_info["name"]] = device_info

    return devices


def _macos_pyaudio_devices():
    devices = {_PYAUDIO_NO_DEVICE_INFO["name"]: _PYAUDIO_NO_DEVICE_INFO}

    for device_index, device_info in enumerate(_pyaudio_devices_by_api(pa.paCoreAudio)):
        # print(device_info)
        device_info["index"] = device_index

        # TODO: Check if default device

        if "NoMachine" not in device_info["name"]:
            devices[device_info["name"]] = device_info

    return devices


def _windows_pyaudio_devices():
    devices = {_PYAUDIO_NO_DEVICE_INFO["name"]: _PYAUDIO_NO_DEVICE_INFO}

    for device_info in _pyaudio_devices_by_api(pa.paDirectSound):
        # print(device_info)

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
    logger.debug("PyAudio session created")
    return session


def _destroy_pyaudio_session(session):
    session.terminate()
    logger.debug("PyAudio session destroyed")







if __name__ == "__main__":
    # import pprint
    import pathlib
    # import time

    # pp = pprint.PrettyPrinter(indent=4)

    # pp.pprint(AudioCapture.available_input_devices())

    # capture = AudioCapture.from_input_device(
    #     in_name="PI world v1: USB Audio (hw:2,0)",
    #     out_path=str(pathlib.Path(__file__).with_suffix(".new_api.out.mp4").absolute())
    # )

    # try:
    #     capture.start()
    #     while True:
    #         time.sleep(0.1)
    # except KeyboardInterrupt:
    #     pass
    # finally:
    #     capture.stop()

    test_async_pyaudio_api(
        in_name="PI world v1: USB Audio (hw:2,0)",
        out_path=str(pathlib.Path(__file__).with_suffix(".new_api.out.mp4").absolute()),
    )

