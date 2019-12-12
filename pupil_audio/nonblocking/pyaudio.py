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
        self._frame_rate = int(frame_rate) if frame_rate else None
        self._channels = int(channels) if channels else None
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

        if self._internal_queue is not None:
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


class PyAudioDelayedDeviceSource(HeartbeatMixin, PyAudioDeviceSource):
    def __init__(self, *args, device_index, device_name, device_monitor=None, **kwargs):
        # This value doesn't make sense, since it will be updated based on device_name
        device_index = None
        super().__init__(*args, device_index, **kwargs)
        self.device_name = device_name
        self.device_monitor = device_monitor or PyAudioBackgroundDeviceMonitor()
        assert isinstance(self.device_monitor, PyAudioBackgroundDeviceMonitor)
        self._wait_for_device_thread = None
        self._wait_for_device = threading.Event()

    @property
    def _is_waiting_for_device(self) -> bool:
        return self._wait_for_device.is_set()

    def start(self):
        if self._is_waiting_for_device or self.is_running:
            return
        self.stop()
        self._wait_for_device.set()
        self._wait_for_device_thread = threading.Thread(
            name=type(self).__name__,
            target=self.__delayed_start,
            args=(self.device_name,),
            daemon=True,
        )
        self._wait_for_device_thread.start()
        # Don't call `super().start()` here!
        # It's called in `__delayed_start` once the _device_index is configured

    def stop(self):
        self.heartbeat_complete()
        self._wait_for_device.clear()
        if self._wait_for_device_thread is not None:
            self._wait_for_device_thread.join()
            self._wait_for_device_thread = None
        super().stop()

    def _stream_callback(self, *args, **kwargs):
        self.heartbeat()
        return super()._stream_callback(*args, **kwargs)

    def on_input_device_connected(self, device_info):
        pass

    def on_input_device_disconnected(self):
        pass

    def on_heartbeat_unexpectedly_stopped(self):
        self.on_input_device_disconnected()
        self.cleanup()

    def __delayed_start(self, device_name, freq_hz=0.3, time_fn=None):
        exec_time = 1./freq_hz
        time_fn = time_fn or time.monotonic

        monitor_was_already_running = self.device_monitor.is_running

        if not monitor_was_already_running:
            self.device_monitor.start()

        device_info = None

        while self._wait_for_device.is_set():
            start_time = time_fn()

            try:
                self.device_monitor.update()
                device_info = self.device_monitor.devices_by_name.get(device_name, None)
                if device_info is not None:
                    break
            except Exception as err:
                logger.error(err)

            remaining_time = exec_time - (time_fn() - start_time)
            if remaining_time > 0:
                time.sleep(remaining_time)

        if not monitor_was_already_running:
            self.device_monitor.stop()

        if device_info is None:
            return

        self._device_index = device_info.index
        self._frame_rate = int(device_info.default_sample_rate)
        self._channels = int(device_info.max_input_channels)
        self._wait_for_device_thread = None

        self.on_input_device_connected(device_info)

        super().start()
