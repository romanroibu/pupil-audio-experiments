def main():
    import time
    import logging

    import numpy as np

    from pupil_audio.blocking import Control, PyAudioDeviceInputStream, PyAVFileOutputStream

    from pupil_audio.blocking.pyav import logger as pyav_logger
    from pupil_audio.blocking.pyaudio import logger as pyaudio_logger

    import examples.utils as example_utils


    pyav_logger.setLevel(logging.DEBUG)
    pyaudio_logger.setLevel(logging.DEBUG)

    input_name = example_utils.get_user_selected_input_name()
    output_path = example_utils.get_output_file_path(__file__, input_name, ext="mp4")

    dtype = np.dtype('int16')
    chunk_size = 1024

    input_stream = PyAudioDeviceInputStream(
        name=input_name,
        dtype=dtype,
    )

    channels = input_stream.channels
    frame_rate = input_stream.frame_rate

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
