import logging
import xml.etree.ElementTree as ET

import pandas as pd

MISSVAL = -99.0


def add_xml_series(root, df, parameter_id, units, series_type="instantaneous"):
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
        series = ET.SubElement(root, "series")
        header = ET.SubElement(series, "header")
        ET.SubElement(header, "type").text = series_type
        ET.SubElement(header, "locationId").text = location_id
        ET.SubElement(header, "parameterId").text = parameter_id
        ET.SubElement(
            header, "timeStep", unit="second", multiplier=str(timestep_seconds)
        )
        ET.SubElement(
            header,
            "startDate",
            date=start_time.strftime("%Y-%m-%d"),
            time=start_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(
            header,
            "endDate",
            date=end_time.strftime("%Y-%m-%d"),
            time=end_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(
            header,
            "forecastDate",
            date=start_time.strftime("%Y-%m-%d"),
            time=start_time.strftime("%H:%M:%S"),
        )
        ET.SubElement(header, "missVal").text = str(MISSVAL)
        ET.SubElement(header, "stationName").text = location_id
        ET.SubElement(header, "units").text = units
        for timestamp, value in df[col].items():
            if pd.isna(value):
                ET.SubElement(
                    series,
                    "event",
                    date=timestamp.strftime("%Y-%m-%d"),
                    time=timestamp.strftime("%H:%M:%S"),
                    value=str(MISSVAL),
                    flag="8",
                )
            else:
                ET.SubElement(
                    series,
                    "event",
                    date=timestamp.strftime("%Y-%m-%d"),
                    time=timestamp.strftime("%H:%M:%S"),
                    value=str(value),
                )
