import queue
import threading
from fractions import Fraction

import av


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

        while True:
            try:
                in_frame, in_timestamp = self._queue.get_nowait()
            except queue.Empty:
                if self.is_running:
                    continue
                else:
                    break

            out_frame, out_timestamp = self._transcoder.transcode(in_frame, in_timestamp)

            out_frame.pts = None

            for packet in stream.encode(out_frame):
                container.mux(packet)

        for packet in stream.encode(None):
            container.mux(packet)

        container.close()
