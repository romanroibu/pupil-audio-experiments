import queue

import pyaudio

from pupil_audio.utils.pyaudio import PyAudioManager, HostApiInfo, DeviceInfo, TimeInfo


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
