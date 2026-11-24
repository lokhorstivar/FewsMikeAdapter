"""Write observed water levels (FEWS PI-XML) to the DFS0 files used by MIKE+ data assimilation.

One ``<locationId>.dfs0`` file is written per location, with a single water-level
item. Missing observations are kept as delete values (they are not filled), so the
data assimilation simply does not update at those times. Every file covers the full
simulation period on a regular time step, also when a station has no data at all.
"""

import logging
import os

import mikeio
import numpy as np
import pandas as pd
from mikeio import EUMType, EUMUnit

from .pixml_to_dfs0 import read_pixml

logger = logging.getLogger(__name__)


def write_da_observations(
    pixml_file: str,
    output_folder: str,
    start_time,
    end_time,
    item_name: str = "Water Level",
    timestep: str = "1h",
    locations=None,
) -> list:
    """Write one water-level DFS0 per location in ``pixml_file`` to ``output_folder``.

    ``locations``: optional list of location ids that must always get a file
    (an all-missing file is written when FEWS exported no data for them).
    Returns a dict {written file: number of valid values}.
    """
    os.makedirs(output_folder, exist_ok=True)
    groups = read_pixml(pixml_file) if os.path.isfile(pixml_file) else {}
    if not groups:
        logger.warning(f"No observations found in {pixml_file}")
    frames = [df for df in groups.values()]
    obs = pd.concat(frames, axis=1) if frames else pd.DataFrame()
    obs = obs.T.groupby(level=0).first().T if not obs.empty else obs  # one column per location

    index = pd.date_range(pd.Timestamp(start_time).floor(timestep),
                          pd.Timestamp(end_time).ceil(timestep), freq=timestep)
    wanted = list(dict.fromkeys(list(obs.columns) + list(locations or [])))

    written = {}
    for location in wanted:
        if location in obs.columns:
            series = obs[location].dropna()
            series = series[~series.index.duplicated()]
            values = series.reindex(index.union(series.index)).interpolate(
                method="time", limit=1, limit_area="inside"
            ).reindex(index)
        else:
            values = pd.Series(np.nan, index=index)
        n_obs = int(values.notna().sum())
        if n_obs == 0:
            logger.warning(f"DA station {location}: no observations in the simulation period")
        da = mikeio.DataArray(
            data=values.values.astype(float),
            time=index,
            item=mikeio.ItemInfo(item_name, EUMType.Water_Level, EUMUnit.meter),
        )
        dfs0 = os.path.join(output_folder, f"{location}.dfs0")
        mikeio.Dataset([da]).to_dfs(dfs0)
        logger.info(f"Written DA observations: {dfs0} ({n_obs} values)")
        written[dfs0] = n_obs
    return written
