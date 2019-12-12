import time
import queue
import threading
from pathlib import Path
from fractions import Fraction

import av
import numpy as np


class PyAVFileSink():
    def __init__(self, file_path, transcoder, in_queue, timestamps_path=None):
        file_path = Path(file_path)
        self._file_path = str(file_path)
        self._timestamps_path = timestamps_path or str(file_path.with_name(file_path.stem + "_timestamps").with_suffix(".npy"))
        self._timestamps_list = None
        self._transcoder = transcoder
        self._queue = in_queue
        self._thread = None
        self._running = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self):
        if self.is_running:
            return
        self._timestamps_list = []
        self._running.set()
        self._thread = threading.Thread(
            name=type(self).__name__,
            target=self._record_loop,
            args=(self._file_path, self._transcoder.frame_rate),
            daemon=True,
        )
        self._thread.start()
        self._transcoder.start()

    def stop(self):
        if not self.is_running:
            return
        self._running.clear()
        self._transcoder.stop()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        if self._timestamps_list is not None:
            timestamps = np.array(self._timestamps_list)
            np.save(self._timestamps_path, timestamps)
            self._timestamps_list = None

    def _record_loop(self, file_path, frame_rate):
        container = av.open(file_path, 'w')
        stream = container.add_stream('aac', rate=float(frame_rate))
        should_flush_stream = False

        while True:
            try:
                in_frame, in_timestamp = self._queue.get(timeout=0.01)
            except queue.Empty:
                if self.is_running:
                    continue
                else:
                    break

            out_frame, out_timestamp = self._transcoder.transcode(in_frame, in_timestamp)

            for packet in stream.encode(out_frame):
                container.mux(packet)
                should_flush_stream = True

            self._timestamps_list.append(out_timestamp)

        if should_flush_stream:
            for packet in stream.encode(None):
                container.mux(packet)

        container.close()
