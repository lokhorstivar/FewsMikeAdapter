"""
Module to convert MIKE-NAM results to PI XML.
"""

import logging
import xml.etree.ElementTree as ET

import pandas as pd
from mikeio1d import Res1D

from utils import add_xml_series


def mikenam_to_pixml(
    res1d_file: str,
    output_xml: str,
    parameter_id: str = "Q.sim",
    units: str = "m3/s",
    dva_type: str = "instantaneous",
) -> None:
    """
    Convert NAM TotalRunOff to PI XML.
    """
    logging.info(f"Opening {res1d_file}")
    res = Res1D(res1d_file)
    logging.info("Reading catchment runoff...")
    df = res.catchments.TotalRunOff.read()
    NS = {"pi": "http://www.wldelft.nl/fews/PI"}
    root = ET.Element("PIroot", xmlns=NS["pi"])
    add_xml_series(root, df, parameter_id=parameter_id, units=units, series_type=dva_type)
    tree = ET.ElementTree(root)
    tree.write(output_xml, encoding="UTF-8", xml_declaration=True)
    logging.info(f"Written: {output_xml}")
