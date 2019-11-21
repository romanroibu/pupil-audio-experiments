import sys
import time
import logging
import pathlib

import pyaudio

from _pupil_audio import Control
from _pupil_audio import PyAudioDeviceInputStream
from _pupil_audio import WaveFileOutputStream
from _pupil_audio import wave as pupil_audio_wave  # For logger
from _pupil_audio import pyaudio as pupil_audio_pyaudio  # For logger


logger = logging.getLogger(__name__)


logger.setLevel(logging.DEBUG)
pupil_audio_wave.logger.setLevel(logging.DEBUG)
pupil_audio_pyaudio.logger.setLevel(logging.DEBUG)


def append_to_file_name(path, name_suffix):
    cls = type(path)
    path = pathlib.Path(path)
    dir_path = path.parent
    name, *tail = path.name.split(".")
    name += name_suffix
    path = dir_path.joinpath(".".join([name]+tail))
    path = cls(path)
    return path


def main(
    output_path=str(pathlib.Path(__file__).with_suffix(".out.wav").absolute()),
    format=pyaudio.paInt16,
    channels=2,
    frame_rate=44100,
    chunk_size=1024,
):
    input_names = [device_info["name"] for device_info in PyAudioDeviceInputStream.enumerate_devices()]
    default_input_name = PyAudioDeviceInputStream.default_device()["name"]
    print(default_input_name)

    print("-" * 80)
    print("PLEASE SELECT INPUT DEVICE:")
    for index, name in enumerate(input_names):
        default_flag = "D" if name == default_input_name else " "
        print(f"\t[{index}] {default_flag}: {name}")

    try:
        input_name = input_names[int(input(">>> "))]
    except (ValueError, IndexError):
        print("Invalid input device number. Try again.")
        exit(-1)

    print("-" * 80)

    # Append the input name to the output file name in the output path
    output_path = append_to_file_name(output_path, " " + input_name)

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
        logger.info(f"Output file written to: {output_path}")


if __name__ == "__main__":
    main()
