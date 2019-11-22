"""
PyAudio Example: Make a wire between input and output (i.e., record a
few samples and play them back immediately).

This is the callback (non-blocking) version.
"""
import pprint
import pyaudio
import time

WIDTH = 2
CHANNELS = 2
RATE = 44100

p = pyaudio.PyAudio()

pp = pprint.PrettyPrinter(indent=4)


def key_property(key: str, **kwargs):
    is_readonly = kwargs.get("readonly", False)
    assert isinstance(is_readonly, bool)

    use_default = "default" in kwargs
    default = kwargs.get("default", None)

    should_typecheck = "type" in kwargs
    klass = kwargs.get("type", None)

    def fget(self):
        try:
            return self[key]
        except KeyError:
            if use_default:
                return default
            else:
                raise

    def fset(self, value):
        if should_typecheck and not isinstance(value, klass):
            raise TypeError(f"Expected value of type \"{klass}\", but got value of type \"{type(value)}\"")
        self[key] = value

    if is_readonly:
        return property(fget=fget)
    else:
        return property(fget=fget, fset=fset, fdel=None)


class TimeInfo(dict):
    current_time = key_property("current_time", type=float, readonly=True)
    input_buffer_adc_time = key_property("input_buffer_adc_time", type=float, readonly=True)
    output_buffer_dac_time = key_property("output_buffer_dac_time", type=float, readonly=True)


def input_callback(in_data, frame_count, time_info, status):
    time_info = TimeInfo(time_info)
    print(f"FRAME_COUNT: {frame_count}")
    print(f"TIME_INFO: {time_info}")
    print(f"TIME_INFO.current_time: {time_info.current_time}")
    print(f"TIME_INFO.input_buffer_adc_time: {time_info.input_buffer_adc_time}")
    print(f"TIME_INFO.output_buffer_dac_time: {time_info.output_buffer_dac_time}")
    print(f"STATUS: {status}")
    # print(f"STREAM TIME: {input_stream.get_time()}")
    print("-" * 80)
    return (in_data, pyaudio.paContinue)

input_stream = p.open(
    format=p.get_format_from_width(WIDTH),
    channels=CHANNELS,
    rate=RATE,
    input=True,
    stream_callback=input_callback
)

# print(f"===> STREAM TIME BEFORE START: {input_stream.get_time()}")
input_stream.start_stream()

while input_stream.is_active():
    time.sleep(0.1)
    # print(f"===> STREAM TIME BEFORE START: {input_stream.get_time()}")

input_stream.stop_stream()
input_stream.close()

p.terminate()
