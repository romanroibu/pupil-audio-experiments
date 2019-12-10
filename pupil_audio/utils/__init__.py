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

    heartbeat_timeout = lazy_property(lambda self: 5, type=float)

    def heartbeat(self):
        if self._heartbeat_is_running.is_set():
            self._heatbeat_timer.cancel()
        self._heatbeat_timer = self._create_heartbeat_timer()
        self._heatbeat_timer.start()
        self._heartbeat_is_running.set()

    def on_heartbeat_stopped(self):
        pass

    # Private

    _heartbeat_is_running = lazy_property(lambda self: threading.Event())

    def _create_heartbeat_timer(self):
        return threading.Timer(self.heartbeat_timeout, self._on_heartbeat_timeout)

    def _on_heartbeat_timeout(self):
        self._heartbeat_is_running.clear()
        self._heatbeat_timer.cancel()
        del self._heartbeat_is_running
        del self._heatbeat_timer
        self.on_heartbeat_stopped()
