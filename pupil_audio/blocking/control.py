import logging
import threading


logger = logging.getLogger(__name__)


class Control:

    def __init__(self):
        self._flag = threading.Event()
        self._thread = None
        self.stop()

    def start(self, *args, **kwargs):
        self._flag.set()

        self._thread = threading.Thread(
            target=self._process,
            name="Capture",
            args=args,
            kwargs=kwargs,
        )

        self._thread.start()

    def stop(self):
        self._flag.clear()
        if self._thread is not None:
            self._thread.join()

    def _process(self, input_stream, output_stream, channels, chunk_size):
        try:
            logger.debug("Recording started")
            while self._flag.is_set():
                data = input_stream.read_decoded(chunk_size)
                output_stream.write_decoded(data)
            logging.debug("Recording finished")
        finally:
            input_stream.close()
            output_stream.close()


# TODO: Register atexit callback to ensure stop is called for all instances of Control
