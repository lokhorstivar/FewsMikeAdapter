"""Shared helpers for writing FEWS PI-XML time series."""

import xml.etree.ElementTree as ET

import pandas as pd

PI = "http://www.wldelft.nl/fews/PI"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
MISSVAL = -99.0

ET.register_namespace("", PI)
ET.register_namespace("xsi", XSI)


def new_pi_timeseries_root(time_zone: str = "0.0") -> ET.Element:
    """Create an empty PI <TimeSeries> root element (PI version 1.8)."""
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
    ET.SubElement(root, f"{{{PI}}}timeZone").text = time_zone
    return root


def write_pi_xml(root: ET.Element, output_xml: str) -> None:
    """Write a PI-XML tree to file (UTF-8 with XML declaration)."""
    ET.ElementTree(root).write(output_xml, encoding="UTF-8", xml_declaration=True)


def add_xml_series(root, df, parameter_id, units, series_type="instantaneous"):
    """Add one PI <series> per column of ``df`` (time index) to ``root``."""
    if len(df.index) < 2:
        timestep_seconds = 3600
    else:
        timestep_seconds = int((df.index[1] - df.index[0]).total_seconds())

    start_time = df.index.min()
    end_time = df.index.max()

    for col in df.columns:
        location_id = str(col)
        if ":" in location_id:
            location_id = location_id.split(":", 1)[1]

        series = ET.SubElement(root, f"{{{PI}}}series")
        header = ET.SubElement(series, f"{{{PI}}}header")

        ET.SubElement(header, f"{{{PI}}}type").text = series_type
        ET.SubElement(header, f"{{{PI}}}locationId").text = location_id
        ET.SubElement(header, f"{{{PI}}}parameterId").text = parameter_id
        ET.SubElement(
            header,
            f"{{{PI}}}timeStep",
            unit="second",
            multiplier=str(timestep_seconds),
        )
        ET.SubElement(
            header,
            f"{{{PI}}}startDate",
            date=start_time.strftime("%Y-%m-%d"),
            time=start_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(
            header,
            f"{{{PI}}}endDate",
            date=end_time.strftime("%Y-%m-%d"),
            time=end_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(
            header,
            f"{{{PI}}}forecastDate",
            date=start_time.strftime("%Y-%m-%d"),
            time=start_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(header, f"{{{PI}}}missVal").text = str(MISSVAL)
        ET.SubElement(header, f"{{{PI}}}stationName").text = location_id
        ET.SubElement(header, f"{{{PI}}}units").text = units

        for timestamp, value in df[col].items():
            attrs = {
                "date": timestamp.strftime("%Y-%m-%d"),
                "time": timestamp.strftime("%H:%M:%S"),
                "value": str(MISSVAL) if pd.isna(value) else str(value),
            }
            if pd.isna(value):
                attrs["flag"] = "8"
            ET.SubElement(series, f"{{{PI}}}event", **attrs)
