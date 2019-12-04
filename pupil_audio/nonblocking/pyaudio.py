import time
import queue
import logging
import threading
import typing as T

import pyaudio

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
            self._session = PyAudioManager.acquire_shared_instance()
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

    def stop(self):
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._session is not None:
            PyAudioManager.release_shared_instance(self._session)
            self._session = None

    def _stream_callback(self, in_data, frame_count, time_info, status):
        time_info = TimeInfo(time_info)
        bytes_per_channel = pyaudio.get_sample_size(self._format)
        theoretic_len = frame_count * self._channels * bytes_per_channel
        assert theoretic_len == len(in_data)

        try:
            self._queue.put_nowait((in_data, time_info))
        except queue.Full:
            print(f"!!!!!!!!!!!!!!!!!!!!!! FRAME DROPPED")
            # TODO: Log warning about the queue being full
            pass

        return (None, pyaudio.paContinue)
