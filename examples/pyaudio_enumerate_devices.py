import pprint

from _pupil_audio import PyAudioDeviceInputStream
from _pupil_audio import PyAudioDeviceOutputStream


def main():
    input_devices = PyAudioDeviceInputStream.enumerate_devices()
    output_devices = PyAudioDeviceOutputStream.enumerate_devices()

    pp = pprint.PrettyPrinter(indent=4)

    print("-" * 80)

    print("INPUT DEVICES:")
    pp.pprint(input_devices)

    print("-" * 80)

    print("OUTPUT DEVICES:")
    pp.pprint(output_devices)

    print("-" * 80)


if __name__ == "__main__":
    main()
