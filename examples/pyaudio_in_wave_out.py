import sys
import time
import pathlib

import pyaudio

from _pupil_audio import Control
from _pupil_audio import PyAudioDeviceInputStream
from _pupil_audio import WaveFileOutputStream


def main(
    input_name="Default",
    output_path=str(pathlib.Path(__file__).with_suffix(".out.wav").absolute()),
    format=pyaudio.paInt16,
    channels=2,
    frame_rate=44100,
    chunk_size=1024,
):
    input_stream = PyAudioDeviceInputStream(
        name=input_name,
        channels=channels,
        frame_rate=frame_rate,
        format=format,
    )

    output_stream = WaveFileOutputStream(
        path=output_path,
        channels=channels,
        frame_rate=frame_rate,
        sample_width=input_stream.sample_width,
        format=format,
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
