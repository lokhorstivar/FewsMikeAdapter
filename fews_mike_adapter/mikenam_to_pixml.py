
"""
Module to convert MIKE11 results to PI XML.
"""
import logging
import xml.etree.ElementTree as ET

import pandas as pd
from mikeio1d import Res1D

from utils import add_xml_series

PI = "http://www.wldelft.nl/fews/PI"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", PI)
ET.register_namespace("xsi", XSI)

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
    print(df)
    root = ET.Element(
        f"{{{PI}}}TimeSeries",
        {
            "version": "1.8",
            f"{{{XSI}}}schemaLocation": (
                "http://www.wldelft.nl/fews/PI "
                "https://fewsdocs.deltares.nl/schemas/version1.0/pi-schemas/pi_timeseries.xsd"
            ),
        },
    )
    ET.SubElement(root, f"{{{PI}}}timeZone").text = "0.0"
    
    add_xml_series(root, df, parameter_id=parameter_id, units=units, series_type=dva_type)
    tree = ET.ElementTree(root)
    tree.write(output_xml, encoding="UTF-8", xml_declaration=True)
    logging.info(f"Written: {output_xml}")
