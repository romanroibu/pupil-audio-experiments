import logging
import platform
import contextlib
import threading
import typing as T

import pyaudio

from pupil_audio.utils import key_property


logger = logging.getLogger(__name__)


class UnsupportedOperatingSystem(NotImplementedError):
    def __init__(self):
        super().__init__("Unsupported operating system")


class TimeInfo(dict):
    """
    http://www.portaudio.com/docs/v19-doxydocs/structPaStreamCallbackTimeInfo.html
    """
    current_time           = key_property("current_time",           type=float, readonly=True)
    input_buffer_adc_time  = key_property("input_buffer_adc_time",  type=float, readonly=True)
    output_buffer_dac_time = key_property("output_buffer_dac_time", type=float, readonly=True)


class HostApiInfo(dict):
    """
    http://www.portaudio.com/docs/v19-doxydocs/structPaHostApiInfo.html
    """
    name                            = key_property("name",                  type=str, readonly=True)
    type                            = key_property("type",                  type=int, readonly=True)
    index                           = key_property("index",                 type=int, readonly=True)
    device_count                    = key_property("deviceCount",           type=int, readonly=True, default=0)
    default_input_device_index      = key_property("defaultInputDevice",    type=int, readonly=True, default=None)
    default_output_device_index     = key_property("defaultOutputDevice",   type=int, readonly=True, default=None)
    structVersion                   = key_property("structVersion",         type=int,   readonly=True)

    # Public

    @staticmethod
    def supported() -> T.Iterator["HostApiInfo"]:
        with PyAudioManager.shared_instance() as manager:
            api_count = manager.get_host_api_count()
            for api_index in range(api_count):
                yield HostApiInfo._find_with_api_index(api_index)

    @staticmethod
    def default() -> T.Optional["HostApiInfo"]:
        if platform.system() == "Linux":
            return HostApiInfo._default_on_linux()
        elif platform.system() == "Darwin":
            return HostApiInfo._default_on_macos()
        elif platform.system() == "Windows":
            return HostApiInfo._default_on_windows()
        else:
            raise UnsupportedOperatingSystem()

    def enumerate_devices(self) -> T.Iterator["DeviceInfo"]:
        with PyAudioManager.shared_instance() as manager:
            for device_index in range(self.device_count):
                try:
                    device_info = manager.get_device_info_by_host_api_device_index(self.index, device_index)
                    yield DeviceInfo(device_info)
                except IOError:
                    pass

    # Private

    @staticmethod
    def _default_on_linux() -> T.Optional["DeviceInfo"]:
        # TODO: Use try other APIs if this ALSA is not available
        return HostApiInfo._find_with_api_type(pyaudio.paALSA)

    @staticmethod
    def _default_on_macos() -> T.Optional["DeviceInfo"]:
        # TODO: Use try other APIs if this CoreAudio is not available
        return HostApiInfo._find_with_api_type(pyaudio.paCoreAudio)

    @staticmethod
    def _default_on_windows() -> T.Optional["DeviceInfo"]:
        # TODO: Use try other APIs if this DirectSound is not available
        return HostApiInfo._find_with_api_type(pyaudio.paDirectSound)

    @staticmethod
    def _find_with_api_type(api_type):
        with PyAudioManager.shared_instance() as manager:
            try:
                api_info = manager.get_host_api_info_by_type(api_type)
                return HostApiInfo(api_info)
            except IOError:
                return None

    @staticmethod
    def _find_with_api_index(api_index):
        with PyAudioManager.shared_instance() as manager:
            try:
                api_info = manager.get_host_api_info_by_index(api_index)
                return HostApiInfo(api_info)
            except IOError:
                return None


class DeviceInfo(dict):
    """
    http://www.portaudio.com/docs/v19-doxydocs/structPaDeviceInfo.html
    """
    name                            = key_property("name",                      type=str,   readonly=True)
    index                           = key_property("index",                     type=int,   readonly=True)
    host_api_index                  = key_property("hostApi",                   type=int,   readonly=True)
    max_input_channels              = key_property("maxInputChannels",          type=int,   readonly=True, default=0)
    max_output_channels             = key_property("maxOutputChannels",         type=int,   readonly=True, default=0)
    default_sample_rate             = key_property("defaultSampleRate",         type=float, readonly=True)
    default_low_input_latency       = key_property("defaultLowInputLatency",    type=float, readonly=True)
    default_low_output_latency      = key_property("defaultLowOutputLatency",   type=float, readonly=True)
    default_high_input_latency      = key_property("defaultHighInputLatency",   type=float, readonly=True)
    default_high_oOutput_latency    = key_property("defaultHighOutputLatency",  type=float, readonly=True)
    structVersion                   = key_property("structVersion",             type=int,   readonly=True)

    # Public

    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0

    @staticmethod
    def default_input() -> T.Optional["DeviceInfo"]:
        return DeviceInfo._default_device(getter=pyaudio.PyAudio.get_default_input_device_info)

    @staticmethod
    def default_output() -> T.Optional["DeviceInfo"]:
        return DeviceInfo._default_device(getter=pyaudio.PyAudio.get_default_output_device_info)

    @staticmethod
    def named_input(name: str) -> "DeviceInfo":
        return DeviceInfo._named_device_or_raise_exception(name, DeviceInfo.inputs_by_name())

    @staticmethod
    def named_output(name: str) -> "DeviceInfo":
        return DeviceInfo._named_device_or_raise_exception(name, DeviceInfo.outputs_by_name())

    @staticmethod
    def inputs_by_name() -> T.Mapping[str, "DeviceInfo"]:
        return {name: device_info for name, device_info in DeviceInfo.devices_by_name().items() if device_info.max_input_channels > 0}

    @staticmethod
    def outputs_by_name() -> T.Mapping[str, "DeviceInfo"]:
        return {name: device_info for name, device_info in DeviceInfo.devices_by_name().items() if device_info.max_output_channels > 0}

    @staticmethod
    def devices_by_name() -> T.Mapping[str, "DeviceInfo"]:
        return {device_info.name: device_info for device_info in DeviceInfo.enumerate()}

    @staticmethod
    def enumerate() -> T.Iterator["DeviceInfo"]:
        api_info = HostApiInfo.default()

        if not api_info:
            # TODO: Log that no API is available
            return []

        device_infos = api_info.enumerate_devices()

        if platform.system() == "Linux":
            yield from DeviceInfo._filter_on_linux(device_infos)
        elif platform.system() == "Darwin":
            yield from DeviceInfo._filter_on_macos(device_infos)
        elif platform.system() == "Windows":
            yield from DeviceInfo._filter_on_windows(device_infos)
        else:
            raise UnsupportedOperatingSystem()

    # Private

    @staticmethod
    def _default_device(getter: T.Callable[[pyaudio.PyAudio], dict]) -> T.Optional["DeviceInfo"]:
        with PyAudioManager.shared_instance() as manager:
            try:
                return DeviceInfo(getter(manager))
            except IOError:
                return None

    @staticmethod
    def _named_device_or_raise_exception(name: str, devices_by_name: T.Mapping[str, "DeviceInfo"]) -> "DeviceInfo":
        try:
            return devices_by_name[name]
        except KeyError:
            available_devices = ", ".join(sorted(devices_by_name.keys()))
            raise ValueError(f"No device named \"{name}\". Available devices: {available_devices}.")

    @staticmethod
    def _filter_on_linux(device_infos: T.Iterator["DeviceInfo"]) -> T.Iterator["DeviceInfo"]:
        for device_info in device_infos:
            # TODO: Consider ignoring "default" since it sometimes has invalid configuration
            if "hw:" in device_info.name or "default" == device_info.name:
                yield device_info

    @staticmethod
    def _filter_on_macos(device_infos: T.Iterator["DeviceInfo"]) -> T.Iterator["DeviceInfo"]:
        for device_index, device_info in enumerate(device_infos):
            device_info["index"] = device_index # TODO: Check if this is actually needed
            if "NoMachine" not in device_info.name:
                yield device_info

    @staticmethod
    def _filter_on_windows(device_infos: T.Iterator["DeviceInfo"]) -> T.Iterator["DeviceInfo"]:
        for device_info in device_infos:
            yield device_info

    @staticmethod
    def _enumerate_by_api(api: int) -> T.Iterator["DeviceInfo"]:
        with PyAudioManager.shared_instance() as manager:
            api_info = manager.get_host_api_info_by_type(api)
            for device_index in range(api_info["deviceCount"]):
                device_info = manager.get_device_info_by_host_api_device_index(api_info["index"], device_index)
                yield DeviceInfo(device_info)


# TODO: Remove function in favour of using DeviceInfo directly
def get_default_input() -> T.Optional[DeviceInfo]:
    return DeviceInfo.default_input()


# TODO: Remove function in favour of using DeviceInfo directly
def get_default_output() -> T.Optional[DeviceInfo]:
    return DeviceInfo.default_output()


# TODO: Remove function in favour of using DeviceInfo directly
def get_input_by_name(name: str) -> DeviceInfo:
    return DeviceInfo.named_input(name)


# TODO: Remove function in favour of using DeviceInfo directly
def get_output_by_name(name: str) -> DeviceInfo:
    return DeviceInfo.named_output(name)


# TODO: Remove function in favour of using DeviceInfo directly
def get_all_inputs(unowned_session=None) -> T.Mapping[str, DeviceInfo]:
    return DeviceInfo.inputs_by_name()


# TODO: Remove function in favour of using DeviceInfo directly
def get_all_outputs() -> T.Mapping[str, DeviceInfo]:
    return DeviceInfo.outputs_by_name()


# TODO: Remove function in favour of using DeviceInfo directly
def get_all_devices() -> T.Mapping[str, DeviceInfo]:
    return DeviceInfo.devices_by_name()


class PyAudioManager:

    # Public

    @staticmethod
    def acquire_shared_instance() -> T.Optional[pyaudio.PyAudio]:
        if PyAudioManager._manager_lock.acquire():
            # TODO: Send stdout to /dev/null while initializing the session
            manager = pyaudio.PyAudio()
            logger.debug("PyAudioManager acquisition successful")
            PyAudioManager._acquired_managers.add(manager)
            return manager
        else:
            logger.debug("PyAudioManager acquisition failed")
            return None

    @staticmethod
    def release_shared_instance(manager: T.Optional[pyaudio.PyAudio]):
        if manager is None:
            return
        try:
            PyAudioManager._acquired_managers.remove(manager)
        except KeyError:
            raise ValueError("PyAudio manager instance was not acquired with PyAudioManager.acquire_shared_instance()")
        manager.terminate()
        PyAudioManager._manager_lock.release()

    @staticmethod
    @contextlib.contextmanager
    def shared_instance():
        manager = PyAudioManager.acquire_shared_instance()
        try:
            yield manager
        finally:
            PyAudioManager.release_shared_instance(manager)
    
    # Private

    _manager_lock = threading.RLock()
    _acquired_managers = set()


# TODO: Remove function in favour of using PyAudioManager directly
@contextlib.contextmanager
def session_context():
    with PyAudioManager.shared_instance() as manager:
        yield manager


# TODO: Remove function in favour of using PyAudioManager directly
def create_session():
    return PyAudioManager.acquire_shared_instance()


# TODO: Remove function in favour of using PyAudioManager directly
def destroy_session(session):
    PyAudioManager.release_shared_instance(session)
