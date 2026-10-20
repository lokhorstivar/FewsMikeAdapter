"""Reading settings.ini and resolving the paths in it."""

import configparser
from pathlib import Path


def read_settings(path: str) -> configparser.ConfigParser:
    """Read a settings.ini file.

    The folder of the settings file is stored as ``config.base_dir`` so that
    relative paths in the file can be resolved against it (see :func:`resolve_path`).
    """
    settings_file = Path(path)
    if not settings_file.is_file():
        raise FileNotFoundError(f"Settings file not found: {settings_file}")

    config = configparser.ConfigParser()
    config.read(settings_file, encoding="utf-8")
    config.base_dir = settings_file.resolve().parent
    return config


def resolve_path(config: configparser.ConfigParser, value):
    """Return ``value`` as a path relative to the folder of settings.ini.

    Absolute paths and empty values are returned unchanged.
    """
    if not value:
        return value
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str(Path(config.base_dir) / p)


def resolve_executable(config: configparser.ConfigParser, value):
    """Resolve an executable path.

    A relative path is taken relative to settings.ini only if that file exists;
    otherwise it is passed on unchanged (e.g. a name found on PATH).
    """
    if not value:
        return value
    candidate = Path(config.base_dir) / value
    return str(candidate) if candidate.is_file() else value
