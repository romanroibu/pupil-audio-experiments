import queue

import pyaudio

import pupil_audio.utils.pyaudio as pyaudio_utils


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
            self._session = pyaudio_utils.create_session()
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
            pyaudio_utils.destroy_session(self._session)
            self._session = None

    def _stream_callback(self, in_data, frame_count, time_info, status):
        time_info = pyaudio_utils.TimeInfo(time_info)

        timestamp = time_info.input_buffer_adc_time
        # timestamp = time_info.current_time

        try:
            self._queue.put_nowait((in_data, timestamp))
        except queue.Full:
            print(f"!!!!!!!!!!!!!!!!!!!!!! FRAME DROPPED")
            # TODO: Log warning about the queue being full
            pass

        return (None, pyaudio.paContinue)
