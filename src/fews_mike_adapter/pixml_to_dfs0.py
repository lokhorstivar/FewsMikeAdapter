"""Convert FEWS PI-XML time series to MIKE DFS0 files (one file per parameter)."""

import logging
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

NS = {"pi": "http://www.wldelft.nl/fews/PI"}


def get_iteminfo(parameter: str, location: str):
    """Return a mikeio.ItemInfo based on parameter and location."""
    import mikeio
    from mikeio import EUMType, EUMUnit

    p = parameter.lower()
    if p in ["precipitation", "rainfall", "rain", "precip"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Rainfall,
            unit=EUMUnit.millimeter,
            data_value_type="StepAccumulated",
        )
    if p in ["evaporation", "evap", "pet", "referenceevaporation"]:
        return mikeio.ItemInfo(
            name=location,
            itemtype=EUMType.Evaporation,
            unit=EUMUnit.millimeter,
            data_value_type="StepAccumulated",
        )
    if p in ["waterlevel", "h", "stage"]:
        return mikeio.ItemInfo(name=location, itemtype=EUMType.Water_Level, unit=EUMUnit.meter)
    if p in ["temperature", "tp", "temp"]:
        return mikeio.ItemInfo(
            name=location, itemtype=EUMType.Temperature, unit=EUMUnit.degree_Celsius
        )
    logger.warning(f"Unknown parameter '{parameter}'. Writing as Undefined.")
    return mikeio.ItemInfo(location)


def read_pixml(pixml_file: str) -> dict:
    """Read a PI-XML file into ``{parameterId: DataFrame}`` (one column per location)."""
    logger.info(f"Reading PI XML: {pixml_file}")
    root = ET.parse(pixml_file).getroot()

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
            except ValueError:
                value = np.nan
            records.append([timestamp, value])
        if not records:
            continue

        df = pd.DataFrame(records, columns=["time", location]).set_index("time")
        parameter_groups.setdefault(parameter, []).append(df)

    return {
        parameter: pd.concat(frames, axis=1).groupby(level=0).first().sort_index()
        for parameter, frames in parameter_groups.items()
    }


def pixml_to_dfs0(pixml_file: str, output_folder: str) -> list:
    """Convert a PI-XML file to DFS0 files in ``output_folder``.

    One ``<parameterId>.dfs0`` is written per parameter, with one item per location.
    Returns the list of written files.
    """
    import mikeio

    os.makedirs(output_folder, exist_ok=True)
    written = []
    for parameter, df_parameter in read_pixml(pixml_file).items():
        logger.info(f"Processing parameter: {parameter}")
        dataarrays = [
            mikeio.DataArray(
                data=df_parameter[location].values,
                time=df_parameter.index,
                item=get_iteminfo(parameter, location),
            )
            for location in df_parameter.columns
        ]
        dfs0_file = os.path.join(output_folder, f"{parameter}.dfs0")
        mikeio.Dataset(dataarrays).to_dfs(dfs0_file)
        logger.info(f"Written: {dfs0_file} ({len(df_parameter.columns)} stations)")
        written.append(dfs0_file)

    logger.info("Finished pixml_to_dfs0.")
    return written
