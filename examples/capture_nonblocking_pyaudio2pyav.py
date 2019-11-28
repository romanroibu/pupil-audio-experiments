def main(
    in_name,
    out_path,
    frame_rate=None,
):
    import time
    from pupil_audio.nonblocking import PyAudio2PyAVCapture


    capture = PyAudio2PyAVCapture(
        in_name=in_name,
        out_path=out_path,
        frame_rate=frame_rate,
    )

    try:
        capture.start()
        while True:
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
    def cli(frame_rate):
        in_name = example_utils.get_user_selected_input_name()
        out_path = example_utils.get_output_file_path(
            __file__,
            in_name,
            frame_rate,
            ext="mp4"
        )
        main(
            in_name=in_name,
            out_path=out_path,
            frame_rate=frame_rate,
        )

    cli()
