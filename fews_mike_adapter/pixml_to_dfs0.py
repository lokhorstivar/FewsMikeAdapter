
"""
Module to convert PI XML to DFS0.
"""
import logging
import os
import xml.etree.ElementTree as ET

import mikeio
import numpy as np
import pandas as pd
from mikeio import EUMType, EUMUnit

NS = {"pi": "http://www.wldelft.nl/fews/PI"}

def get_iteminfo(parameter: str, location: str) -> mikeio.ItemInfo:
    """
    Return a mikeio.ItemInfo based on parameter and location.
    """
    p = parameter.lower()
    if p in ["precipitation", "rainfall", "rain", "precip"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Rainfall,
            unit=EUMUnit.millimeter,
            data_value_type="StepAccumulated"
        )
    elif p in ["evaporation", "evap", "pet", "referenceevaporation"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Evaporation,
            unit=EUMUnit.millimeter
        )
    elif p in ["waterlevel", "h", "stage"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Water_Level,
            unit=EUMUnit.meter
        )
    elif p in ["temperature", "tp", "temp"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Temperature,
            unit=EUMUnit.degree_Celsius
        )
    else:
        logging.warning(f"Unknown parameter '{parameter}'. Writing as Undefined.")
        return mikeio.ItemInfo(location)

def pixml_to_dfs0(pixml_file: str, output_folder: str) -> None:
    """
    Convert PI XML to DFS0 files.
    """
    logging.info(f"Reading PI XML: {pixml_file}")
    tree = ET.parse(pixml_file)
    root = tree.getroot()
    parameter_groups = {}
    for series in root.findall(".//pi:series", NS):
        header = series.find("pi:header", NS)
        if header is None:
            continue
        parameter = header.find("pi:parameterId", NS).text
        location = header.find("pi:locationId", NS).text
        records = []
        for event in series.findall("pi:event", NS):
            value = event.attrib.get("value")
            if value is None:
                continue
            timestamp = pd.Timestamp(f"{event.attrib['date']} {event.attrib['time']}")
            try:
                value = float(value)
            except:
                value = np.nan
            records.append([timestamp, value])
        if not records:
            continue
        df = pd.DataFrame(records, columns=["time", location])
        df.set_index("time", inplace=True)
        parameter_groups.setdefault(parameter, []).append(df)
    os.makedirs(output_folder, exist_ok=True)
    for parameter, station_dataframes in parameter_groups.items():
        logging.info(f"Processing parameter: {parameter}")
        df_parameter = pd.concat(station_dataframes, axis=1)
        df_parameter = df_parameter.groupby(level=0).first().sort_index()
        dataarrays = []
        for location in df_parameter.columns:
            iteminfo = get_iteminfo(parameter, location)
            logging.info(f"  {location} -> {iteminfo.type} / {iteminfo.unit}")
            da = mikeio.DataArray(
                data=df_parameter[location].values,
                time=df_parameter.index,
                item=iteminfo
            )
            dataarrays.append(da)
        ds = mikeio.Dataset(dataarrays)
        dfs0_file = os.path.join(output_folder, f"{parameter}.dfs0")
        ds.to_dfs(dfs0_file)
        logging.info(f"Written: {dfs0_file} ({len(df_parameter.columns)} stations)")
    logging.info("Finished pixml_to_dfs0.")
