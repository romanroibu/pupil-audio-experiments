import threading


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


def lazy_property(init_fn, **kwargs):
    is_readonly = kwargs.get("readonly", False)
    assert isinstance(is_readonly, bool)

    # TODO: Make this thread-safe

    _storage = None
    _did_init = False

    def fget(self):
        nonlocal _did_init, _storage, init_fn
        if not _did_init:
            _storage = init_fn(self)
            _did_init = True
        return _storage

    def fset(self, value):
        nonlocal _did_init, _storage
        _storage = value
        _did_init = True

    def fdel(self):
        nonlocal _did_init, _storage
        del _storage
        del _did_init

    if is_readonly:
        return property(fget=fget)
    else:
        return property(fget=fget, fset=fset, fdel=fdel)


class HeartbeatMixin:

    # Public

    """
    Time interval after which the `on_heartbeat_unexpectedly_stopped` method is called.
    """
    heartbeat_timeout = lazy_property(lambda self: 5, type=float)

    def heartbeat(self):
        """
        Calling this method signals a running heartbeat, which resets the timer.

        The client of the mixin is responsible to call this method periodically,
        in intervals less than `heartbeat_timeout` to avoid `on_heartbeat_unexpectedly_stopped`
        from being called.
        """
        self.__destroy_heartbeat_timer()
        self.__create_heartbeat_timer()

    def heartbeat_complete(self):
        """
        Calling this method signals a successful completion of the heartbeat sequence.

        The `on_heartbeat_unexpectedly_stopped` will not be called.
        """
        self.__destroy_heartbeat_timer()

    def on_heartbeat_unexpectedly_stopped(self):
        self.__destroy_heartbeat_timer()

    # Private

    __heartbeat_is_running = lazy_property(lambda self: threading.Event())

    def __destroy_heartbeat_timer(self):
        if self.__heartbeat_is_running.is_set():
            self.__heartbeat_is_running.clear()
            self.__heatbeat_timer.cancel()
            self.__heatbeat_timer = None

    def __create_heartbeat_timer(self):
        if not self.__heartbeat_is_running.is_set():
            self.__heartbeat_is_running.set()
            self.__heatbeat_timer = threading.Timer(
                self.heartbeat_timeout, self.on_heartbeat_unexpectedly_stopped
            )
            self.__heatbeat_timer.start()
