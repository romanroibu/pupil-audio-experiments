import pprint
import itertools

import pyaudio


pp = pprint.PrettyPrinter(indent=4)


def get_devices_from_all_apis():
    session = pyaudio.PyAudio()

    result = {}

    try:
        host_api_count = session.get_host_api_count()
        device_count = session.get_device_count()

        api_and_device_indices = itertools.product(range(host_api_count), range(device_count))
        api_and_device_indices = sorted(api_and_device_indices)

        for host_api_index, host_api_device_index in api_and_device_indices:

            host_info = session.get_host_api_info_by_index(host_api_index)
            device_info = session.get_device_info_by_index(host_api_device_index)

            key = (host_info["name"], device_info["name"])

            try:
                device_info = session.get_device_info_by_host_api_device_index(host_api_index, host_api_device_index)
            except OSError:
                device_info = None

            result[key] = device_info
        
        return result
    finally:
        session.terminate()


def main():

    devices = get_devices_from_all_apis()

    print("-" * 80)
    print("DEVICES:")
    pp.pprint(devices)
    print("-" * 80)


if __name__ == "__main__":
    main()
