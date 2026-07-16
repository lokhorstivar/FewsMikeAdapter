
"""
Module to convert MIKE11 results to PI XML.
"""
import logging
import xml.etree.ElementTree as ET

import pandas as pd
from mikeio1d import Res1D

from utils import add_xml_series


def mike11_to_pixml(res1d_file: str, output_xml: str) -> None:
    """
    Convert MIKE11 results to PI XML output_xml.
    """
    logging.info(f"Opening {res1d_file}")
    res = Res1D(res1d_file)
    logging.info("Reading water levels...")
    wl_df = res.nodes.WaterLevel.read()
    NS = {"pi": "http://www.wldelft.nl/fews/PI"}
    root = ET.Element("PIroot", xmlns=NS["pi"])
    add_xml_series(root, wl_df, parameter_id="H.sim", units="m")
    tree = ET.ElementTree(root)
    tree.write(output_xml, encoding="UTF-8", xml_declaration=True)
    logging.info(f"Written: {output_xml}")
