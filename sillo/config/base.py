class ConfigBase:
    def __init__(self, config=None, **kwargs):
        data = dict(config or {})
        data.update(kwargs)
        self._config = data

    def __getattr__(self, name):
        if name == "_config":
            raise AttributeError(name)
        return self._config.get(name)

    def to_dict(self):
        return dict(self._config)
