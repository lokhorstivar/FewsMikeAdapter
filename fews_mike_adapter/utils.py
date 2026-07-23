import logging
import xml.etree.ElementTree as ET

import pandas as pd

MISSVAL = -99.0


def add_xml_series(root, df, parameter_id, units, series_type="instantaneous"):
    PI = "http://www.wldelft.nl/fews/PI"

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
