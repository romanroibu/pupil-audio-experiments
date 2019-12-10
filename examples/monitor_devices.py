import time
import pprint

from pupil_audio.nonblocking import PyAudioDeviceMonitor
from pupil_audio.nonblocking import PyAudioBackgroundDeviceMonitor


class _LoggingMixin:
    def log_prefix(self):
        return type(self).__name__

    def print_devices_by_name(self, devices_by_name):
        print("-" * 80)
        print(f"{self.log_prefix()}: {list(devices_by_name.keys())}")

    def update(self):
        super().update()
        self.print_devices_by_name(self.devices_by_name)


class _LoggingDeviceMonitor(_LoggingMixin, PyAudioDeviceMonitor):
    def log_prefix(self):
        return "FOREGROUND"


class _LoggingBackgroundDeviceMonitor(_LoggingMixin, PyAudioBackgroundDeviceMonitor):
    def log_prefix(self):
        return "BACKGROUND"


def main(use_foreground=False, use_background=True, delay=0.3):
    assert use_foreground or use_background, "At least one flag should be true"

    if use_foreground:
        fg_monitor = _LoggingDeviceMonitor()

    if use_background:
        bg_monitor = _LoggingBackgroundDeviceMonitor()
        bg_monitor.start()

    try:
        while True:
            if use_foreground:
                fg_monitor.update()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        if use_foreground:
            fg_monitor.cleanup()
        if use_background:
            bg_monitor.cleanup()


if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--foreground", is_flag=True, help="TODO")
    @click.option("--background", is_flag=True, help="TODO")
    @click.option("--delay", default=0.3, help="TODO")
    def cli(foreground, background, delay):
        main(
            use_foreground=foreground,
            use_background=background,
            delay=delay,
        )

    cli()
