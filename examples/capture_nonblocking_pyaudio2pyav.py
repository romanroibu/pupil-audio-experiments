def main(
    in_name,
    out_path,
    frame_rate=None,
    duration=None,
):
    import time
    from pupil_audio.nonblocking import PyAudio2PyAVCapture

    duration = duration or float("inf")

    capture = PyAudio2PyAVCapture(
        in_name=in_name,
        out_path=out_path,
        frame_rate=frame_rate,
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


if __name__ == "__main__":
    import click
    import examples.utils as example_utils

    @click.command()
    @click.option("--frame_rate", default=None, type=click.INT, help="Frame rate used for the input and output (if not set, the default input frame rate is used)")
    @click.option("--duration", default=None, type=click.FLOAT, help="Duration of the recording (if not set, the user should manually stop the recording with Ctrl+C)")
    def cli(frame_rate, duration):
        duration_str = f"{duration}_sec" if duration else None
        in_name = example_utils.get_user_selected_input_name()
        out_path = example_utils.get_output_file_path(
            __file__,
            in_name,
            frame_rate,
            duration_str,
            ext="mp4"
        )
        main(
            in_name=in_name,
            out_path=out_path,
            frame_rate=frame_rate,
            duration=duration,
        )

    cli()
