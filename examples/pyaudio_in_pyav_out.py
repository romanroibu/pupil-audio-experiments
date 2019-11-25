import sys
import time
import pathlib
import logging

import numpy as np

from _pupil_audio import Control
from _pupil_audio import PyAudioDeviceInputStream
from _pupil_audio import PyAVFileOutputStream
from _pupil_audio import pyav as pupil_audio_pyav  # For logger
from _pupil_audio import pyaudio as pupil_audio_pyaudio  # For logger


pupil_audio_pyav.logger.setLevel(logging.DEBUG)
pupil_audio_pyaudio.logger.setLevel(logging.DEBUG)


def main(
    input_name="Default",
    output_path=str(pathlib.Path(__file__).with_suffix(".out.mp4").absolute()),
    dtype=np.dtype('int16'),
    channels=2,
    frame_rate=44100,
    chunk_size=1024,
):
    input_stream = PyAudioDeviceInputStream(
        name=input_name,
        channels=channels,
        frame_rate=frame_rate,
        dtype=dtype,
    )

    output_stream = PyAVFileOutputStream(
        path=output_path,
        channels=channels,
        frame_rate=frame_rate,
        dtype=dtype,
    )

    control = Control()

    control.start(
        input_stream=input_stream,
        output_stream=output_stream,
        channels=channels,
        chunk_size=chunk_size,
    )

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        control.stop()


if __name__ == "__main__":
    main()
