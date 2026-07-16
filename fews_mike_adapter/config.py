
import configparser

def read_settings(path: str) -> configparser.ConfigParser:
    """
    Read settings.ini file.
    """
    config = configparser.ConfigParser()
    config.read(path)
    return config
