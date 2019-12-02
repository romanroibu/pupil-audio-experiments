import logging
import platform
import contextlib
import typing as T

import pyaudio

from pupil_audio.utils import key_property


logger = logging.getLogger(__name__)


class TimeInfo(dict):
    current_time           = key_property("current_time",           type=float, readonly=True)
    input_buffer_adc_time  = key_property("input_buffer_adc_time",  type=float, readonly=True)
    output_buffer_dac_time = key_property("output_buffer_dac_time", type=float, readonly=True)


class DeviceInfo(dict):
    name           = key_property("name",    type=str, readonly=True)
    index          = key_property("index",   type=int, readonly=True)
    host_api_index = key_property("hostApi", type=int, readonly=True)

    max_input_channels  = key_property("maxInputChannels",  type=int, readonly=True)
    max_output_channels = key_property("maxOutputChannels", type=int, readonly=True)

    default_sample_rate = key_property("defaultSampleRate", type=float, readonly=True)

    default_low_input_latency   = key_property("defaultLowInputLatency",  type=float, readonly=True)
    default_low_oOutput_latency = key_property("defaultLowOutputLatency", type=float, readonly=True)

    default_high_input_latency   = key_property("defaultHighInputLatency",  type=float, readonly=True)
    default_high_oOutput_latency = key_property("defaultHighOutputLatency", type=float, readonly=True)

    structVersion = key_property("structVersion", type=int, readonly=True)


def get_default_input() -> T.Optional[DeviceInfo]:
    return _get_default_device_info(pyaudio.PyAudio.get_default_input_device_info)


def get_default_output() -> T.Optional[DeviceInfo]:
    return _get_default_device_info(pyaudio.PyAudio.get_default_output_device_info)


def _get_default_device_info(f: T.Callable[[pyaudio.PyAudio], dict]) -> T.Optional[DeviceInfo]:
    with session_context() as session:
        try:
            info = f(session)
            return DeviceInfo(info)
        except IOError:
            return None


def get_input_by_name(name: str, session=None) -> DeviceInfo:
    return _get_device_info_by_name(name, get_all_inputs())


def get_output_by_name(name: str, session=None) -> DeviceInfo:
    return _get_device_info_by_name(name, get_all_outputs())


def _get_device_info_by_name(name: str, devices_by_name: T.Mapping[str, DeviceInfo]) -> DeviceInfo:
    try:
        return devices_by_name[name]
    except KeyError:
        available_devices = ", ".join(sorted(devices_by_name.keys()))
        raise ValueError(f"No device named \"{name}\". Available devices: {available_devices}.")


def get_all_inputs(unowned_session=None) -> T.Mapping[str, DeviceInfo]:
    return {k: v for k, v in get_all_devices(unowned_session=unowned_session).items() if v.get("maxInputChannels", 0) > 0}


def get_all_outputs(unowned_session=None) -> T.Mapping[str, DeviceInfo]:
    return {k: v for k, v in get_all_devices(unowned_session=unowned_session).items() if v.get("maxOutputChannels", 0) > 0}


def get_all_devices(unowned_session=None) -> T.Mapping[str, DeviceInfo]:
    if platform.system() == "Linux":
        device_infos = _get_linux_device_infos(unowned_session=unowned_session)
    elif platform.system() == "Darwin":
        device_infos = _get_macos_device_infos(unowned_session=unowned_session)
    elif platform.system() == "Windows":
        device_infos = _get_windows_device_infos(unowned_session=unowned_session)
    else:
        raise NotImplementedError("Unsupported operating system")

    return {info["name"]: DeviceInfo(info) for info in device_infos}


def _get_linux_device_infos(unowned_session=None) -> T.Iterator[dict]:
    for device_info in _get_device_infos_by_api(pyaudio.paALSA, unowned_session=unowned_session):
        if "hw:" in device_info["name"] or "default" == device_info["name"]:
            yield device_info


def _get_macos_device_infos(unowned_session=None) -> T.Iterator[dict]:
    for device_index, device_info in enumerate(_get_device_infos_by_api(pyaudio.paCoreAudio, unowned_session=unowned_session)):
        device_info["index"] = device_index
        if "NoMachine" not in device_info["name"]:
            yield device_info


def _get_windows_device_infos(unowned_session=None) -> T.Iterator[dict]:
    for device_info in _get_device_infos_by_api(pyaudio.paDirectSound, unowned_session=unowned_session):
        yield device_info


def _get_device_infos_by_api(api, unowned_session=None):
    if unowned_session:
        yield from _get_device_infos_by_api_with_unowned_session(api, unowned_session)
    else:
        with session_context() as owned_session:
            yield from _get_device_infos_by_api_with_unowned_session(api, owned_session)


def _get_device_infos_by_api_with_unowned_session(api, unowned_session):
    api_info = unowned_session.get_host_api_info_by_type(api)
    for device_index in range(api_info["deviceCount"]):
        yield unowned_session.get_device_info_by_host_api_device_index(api_info["index"], device_index)


@contextlib.contextmanager
def session_context():
    session = create_session()
    try:
        yield session
    finally:
        destroy_session(session)


def create_session():
    # TODO: Send stdout to /dev/null while initializing the session
    session = pyaudio.PyAudio()
    logger.debug("PyAudio session created")
    return session


def destroy_session(session):
    session.terminate()
    logger.debug("PyAudio session destroyed")
