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
