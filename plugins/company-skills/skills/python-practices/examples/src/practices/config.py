"""Chaining an error with raise ... from."""


class ConfigError(Exception):
    """A configuration value could not be read."""

    def __init__(self, key: str, value: str) -> None:
        super().__init__(f"{key} is not valid: {value!r}")


def load_port(text: str) -> int:
    """Read a port number from the configuration."""
    try:
        return int(text)
    except ValueError as error:
        raise ConfigError("port", text) from error
