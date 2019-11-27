def main():
    import pprint

    from pupil_audio.utils.pyaudio import get_all_inputs, get_all_outputs
    from pupil_audio.utils.pyaudio import get_default_input, get_default_output

    input_devices, output_devices = get_all_inputs(), get_all_outputs()
    input_default, output_default = get_default_input(), get_default_output()

    pp = pprint.PrettyPrinter(indent=4)

    print("-" * 80)

    print(f"### INPUT DEVICES (default = \"{input_default.name}\") ###")
    pp.pprint(input_devices)

    print("-" * 80)

    print(f"### OUTPUT DEVICES (default = \"{output_default.name}\") ###")
    pp.pprint(output_devices)

    print("-" * 80)


if __name__ == "__main__":
    main()
