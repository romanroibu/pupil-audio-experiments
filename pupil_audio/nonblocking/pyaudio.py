import time
import queue
import logging
import threading
import collections
import typing as T

import pyaudio

from pupil_audio.utils import HeartbeatMixin
from pupil_audio.utils.pyaudio import PyAudioManager, HostApiInfo, DeviceInfo, TimeInfo


logger = logging.getLogger(__name__)


class PyAudioDeviceMonitor:

    # Public

    def __init__(self):
        self.__devices_by_name = {}

    @property
    def devices_by_name(self) -> T.Mapping[str, DeviceInfo]:
        return self.__devices_by_name

    @devices_by_name.setter
    def devices_by_name(self, value: T.Mapping[str, DeviceInfo]):
        self.__devices_by_name = value

    def update(self):
        self.devices_by_name = DeviceInfo.devices_by_name()

    def cleanup(self):
        pass


class PyAudioBackgroundDeviceMonitor(PyAudioDeviceMonitor):

    # Public

    def __init__(self, time_fn=time.monotonic):
        super().__init__()
        self.__time_fn = time_fn
        self.__should_run = threading.Event()
        self.__monitor_thread = None
        self.__devices_by_name_lock = threading.RLock()

    @property
    def devices_by_name(self) -> T.Mapping[str, DeviceInfo]:
        with self.__devices_by_name_lock:
            return PyAudioDeviceMonitor.devices_by_name.fget(self)

    @devices_by_name.setter
    def devices_by_name(self, value: T.Mapping[str, DeviceInfo]):
        with self.__devices_by_name_lock:
            PyAudioDeviceMonitor.devices_by_name.fset(self, value)

    @property
    def is_running(self):
        return self.__should_run.is_set()

    def start(self):
        if self.is_running:
            return
        self.__should_run.set()
        self.__monitor_thread = threading.Thread(
            name=f"{type(self).__name__}#{id(self)}",
            target=self.__monitor_loop,
            daemon=True,
        )
        self.__monitor_thread.start()

    def stop(self):
        self.__should_run.clear()
        if self.__monitor_thread is not None:
            self.__monitor_thread.join()
            self.__monitor_thread = None

    def cleanup(self):
        self.stop()

    # Private

    def __monitor_loop(self, freq_hz=0.3):
        exec_time = 1./freq_hz
        time_fn = self.__time_fn

        while self.is_running:
            start_time = time_fn()

            try:
                self.update()
            except Exception as err:
                logger.error(err)

            remaining_time = exec_time - (time_fn() - start_time)
            if remaining_time > 0:
                time.sleep(remaining_time)


class PyAudioDeviceSource:

    def __init__(self, device_index, frame_rate, channels, format, out_queue):
        self._device_index = device_index
        self._frame_rate = int(frame_rate)
        self._channels = channels
        self._format = format
        self._out_queue = out_queue

        self._internal_queue = None
        self._internal_thread = None
        self._internal_is_running = threading.Event()
        self._internal_is_terminated = False

    @property
    def is_running(self) -> bool:
        return self._internal_is_running.is_set()

    def start(self):
        if self._internal_is_terminated:
            raise ValueError("Can't start terminated source")
        self.stop()
        self._internal_queue = queue.Queue()
        self._internal_thread = threading.Thread(
            name=type(self).__name__,
            target=self._internal_signal_handler_loop,
            args=(
                self._internal_is_running,
                self._internal_queue,
                self._out_queue,
                self._channels,
                self._format,
                self._frame_rate,
                self._device_index,
            )
        )
        self._internal_is_running.set()
        self._internal_thread.start()

    def stop(self):
        self._internal_is_running.clear()
        if self._internal_queue is not None:
            self._internal_queue = None
        if self._internal_thread is not None:
            self._internal_thread.join()
            self._internal_thread = None

    def cleanup(self):
        self.stop()
        # After cleanup, the source is considered terminated and shouldn't be used
        self._internal_is_terminated = True

    _ErrorSignal = collections.namedtuple("_ErrorSignal", ["error"])

    _DataSignal = collections.namedtuple("_DataSignal", ["data"])

    def _stream_callback(self, in_data, frame_count, time_info, status):
        try:
            time_info = TimeInfo(time_info)
            bytes_per_channel = pyaudio.get_sample_size(self._format)
            theoretic_len = frame_count * self._channels * bytes_per_channel
            assert theoretic_len == len(in_data)
            out_signal = PyAudioDeviceSource._DataSignal((in_data, time_info))
        except Exception as err:
            out_signal = PyAudioDeviceSource._ErrorSignal(err)

        self._internal_queue.put_nowait(out_signal)
        return (None, pyaudio.paContinue)

    def _internal_signal_handler_loop(self, is_running, internal_queue, out_queue, channels, format, frame_rate, device_index):

        with PyAudioManager.shared_instance() as manager:

            stream = manager.open(
                channels=channels,
                format=format,
                rate=frame_rate,
                input=True,
                input_device_index=device_index,
                stream_callback=self._stream_callback,
            )

            stream.start_stream()

            try:
                while is_running.is_set():
                    try:
                        signal = internal_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if isinstance(signal, PyAudioDeviceSource._DataSignal):
                        out_queue.put_nowait(signal.data)
                    elif isinstance(signal, PyAudioDeviceSource._ErrorSignal):
                        raise signal.error
                    else:
                        raise ValueError(f"Unknown signal: {signal}")
            except Exception as err:
                logger.error(err)

            stream.stop_stream()
            stream.close()


class PyAudioDeviceWithHeartbeatSource(HeartbeatMixin, PyAudioDeviceSource):

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        self.heartbeat_complete()

    def _stream_callback(self, *args, **kwargs):
        self.heartbeat()
        return super()._stream_callback(*args, **kwargs)

    def on_heartbeat_unexpectedly_stopped(self):
        self.cleanup()
