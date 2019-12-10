def main():
    import pprint

    from pupil_audio.utils.pyaudio import DeviceInfo

    input_devices, output_devices = DeviceInfo.inputs_by_name(), DeviceInfo.outputs_by_name()
    input_default, output_default = DeviceInfo.default_input(), DeviceInfo.default_output()

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
