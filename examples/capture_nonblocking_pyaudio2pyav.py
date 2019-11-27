def main():
    import time
    import examples.utils as example_utils
    from pupil_audio.nonblocking import PyAudio2PyAVCapture

    in_name = example_utils.get_user_selected_input_name()
    out_path = example_utils.get_output_file_path(__file__, in_name, ext="mp4")

    capture = PyAudio2PyAVCapture(
        in_name=in_name,
        out_path=out_path
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
    main()
