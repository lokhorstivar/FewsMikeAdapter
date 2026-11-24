"""Read the Delft-FEWS PI run file (exported by the General Adapter)."""

import logging
import xml.etree.ElementTree as ET

import pandas as pd

logger = logging.getLogger(__name__)

NS = {"pi": "http://www.wldelft.nl/fews/PI"}


def read_time0(run_file: str) -> pd.Timestamp:
    """Return the forecast time (time0) from a PI run file.

    The time is returned in the time zone of the run file (normally GMT, the
    same time zone in which the General Adapter exports the forcing).
    """
    root = ET.parse(run_file).getroot()
    el = root.find("pi:time0", NS)
    if el is None:
        raise ValueError(f"No <time0> element found in run file {run_file}")
    time0 = pd.Timestamp(f"{el.attrib['date']} {el.attrib['time']}")
    logger.info(f"Forecast time (time0) from run file: {time0}")
    return time0
