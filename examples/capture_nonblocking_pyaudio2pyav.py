def main(
    in_name,
    out_path,
    frame_rate=None,
    duration=None,
    debug=False
):
    import time
    from pupil_audio.nonblocking import PyAudio2PyAVCapture

    duration = duration or float("inf")

    transcoder_cls = _PyAudio2PyAVCustomTranscoder if debug else None

    _PyAudio2PyAVCustomTranscoder._debug_out_path = out_path

    capture = PyAudio2PyAVCapture(
        in_name=in_name,
        out_path=out_path,
        frame_rate=frame_rate,
        transcoder_cls=transcoder_cls
    )

    start_time = time.monotonic()

    try:
        capture.start()
        while time.monotonic() - start_time < duration:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()


import time
import numpy as np
from pupil_audio.nonblocking.pyaudio2pyav import PyAudio2PyAVTranscoder

class _PyAudio2PyAVCustomTranscoder(PyAudio2PyAVTranscoder):
    _debug_out_path = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self._debug_out_path, f"Please set {type(self).__name__}._debug_out_path"
        self._debug_data_store = _DebugDataStore(self._debug_out_path)

    def transcode(self, in_frame, time_info):
        delay = abs(time_info.current_time - time_info.input_buffer_adc_time)
        self._debug_data_store.write(in_frame, delay)
        return super().transcode(in_frame, time_info)

    def start(self):
        super().start()
        self._debug_data_store.open()

    def stop(self):
        super().stop()
        self._debug_data_store.close()


class _DebugDataStore:
    def __init__(self, out_path):
        from pathlib import Path
        out_path = Path(out_path)
        self.raw_buffer_file_path = str(out_path.with_name(out_path.stem + "_raw_buffer").with_suffix(".dat"))
        self.timestamps_file_path = str(out_path.with_name(out_path.stem + "_timestamps").with_suffix(".npy"))
        self._raw_buffer_file = None
        self._timestamps_list = None

    @property
    def is_opened(self) -> bool:
        return self._raw_buffer_file is None or self._timestamps_list is None

    def open(self):
        if self._raw_buffer_file is None:
            self._raw_buffer_file = open(self.raw_buffer_file_path, 'wb')
        if self._timestamps_list is None:
            self._timestamps_list = []

    def write(self, in_frame, delay):
        if not self.is_opened:
            self.open()

        timestamp = time.monotonic() - delay

        self._raw_buffer_file.write(in_frame)
        self._timestamps_list.append((timestamp, len(in_frame)))

    def close(self):
        if self._raw_buffer_file is not None:
            self._raw_buffer_file.close()
            self._raw_buffer_file = None
        if self._timestamps_list is not None:
            timestamps = np.array(self._timestamps_list)
            np.save(self.timestamps_file_path, timestamps)
            self._timestamps_list = None


if __name__ == "__main__":
    import click
    import examples.utils as example_utils

    @click.command()
    @click.option("--frame_rate", default=None, type=click.INT, help="Frame rate used for the input and output (if not set, the default input frame rate is used)")
    @click.option("--duration", default=None, type=click.FLOAT, help="Duration of the recording (if not set, the user should manually stop the recording with Ctrl+C)")
    @click.option("--debug", is_flag=True, help="If set, captures the raw data from the input used for debugging")
    def cli(frame_rate, duration, debug):
        duration_str = f"{duration}_sec" if duration else None
        debug_str = "debug" if debug else None
        in_name = example_utils.get_user_selected_input_name()
        out_path = example_utils.get_output_file_path(
            __file__,
            in_name,
            frame_rate,
            duration_str,
            debug_str,
            ext="mp4"
        )
        main(
            in_name=in_name,
            out_path=out_path,
            frame_rate=frame_rate,
            duration=duration,
            debug=debug
        )

    cli()
