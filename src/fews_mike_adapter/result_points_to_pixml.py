"""Write MIKE 1D results at result points (river + chainage) to FEWS PI-XML.

The points file is a CSV with the columns ``location_id``, ``river`` and ``chainage``
(other columns are ignored; comma or semicolon separated). In FEWS it is written by an
``exportLocationAttributesCsvActivity`` from the MIKE result points location set, so the
map layer file in FEWS is the only place where the points are defined.
Values are interpolated along the reach at the given chainage.
"""

import logging

import pandas as pd
from mikeio1d import Res1D
from mikeio1d.query import QueryDataReach

from .utils import add_xml_series, new_pi_timeseries_root, write_pi_xml

logger = logging.getLogger(__name__)

TOLERANCE = 1.0  # m, chainage rounding in the points file
DEFAULT_QUANTITIES = {"WaterLevel": ("H.sim", "m"), "Discharge": ("Q.sim", "m3/s")}


def read_points_file(points_file: str) -> pd.DataFrame:
    points = pd.read_csv(points_file, sep=None, engine="python", dtype=str, comment="#")
    points.columns = [c.strip().lower() for c in points.columns]
    missing = {"location_id", "river", "chainage"} - set(points.columns)
    if missing:
        raise ValueError(f"Points file {points_file} misses column(s): {sorted(missing)}")
    points = points[["location_id", "river", "chainage"]].apply(lambda s: s.str.strip())
    points["chainage"] = pd.to_numeric(points["chainage"], errors="coerce")
    bad = points["chainage"].isna() | points["river"].isna() | (points["river"] == "")
    for row in points[bad].itertuples():
        logger.error(f"Point {row.location_id}: no river/chainage, skipped")
    return points[~bad].reset_index(drop=True)


def parse_quantities(text: str = None) -> dict:
    """Parse ``WaterLevel=H.sim:m, Discharge=Q.sim:m3/s`` into a quantity mapping."""
    if not text:
        return dict(DEFAULT_QUANTITIES)
    result = {}
    for part in text.split(","):
        quantity, target = part.split("=")
        parameter, _, units = target.partition(":")
        result[quantity.strip()] = (parameter.strip(), units.strip() or "-")
    return result


def _valid_points(res, points: pd.DataFrame) -> pd.DataFrame:
    """Drop points whose river is not in the model or whose chainage is outside the reach."""
    keep = []
    for row in points.itertuples():
        reach = res.reaches.get(row.river) if hasattr(res.reaches, "get") else None
        if reach is None:
            logger.error(f"Point {row.location_id}: river '{row.river}' not in the model, skipped")
            continue
        start, end = sorted((reach.start_chainage, reach.end_chainage))
        if not (start - TOLERANCE <= row.chainage <= end + TOLERANCE):
            logger.error(
                f"Point {row.location_id}: chainage {row.chainage} outside {row.river} ({start}-{end}), skipped"
            )
            continue
        # a chainage rounded in the points file may fall just outside the reach end
        points.loc[row.Index, "chainage"] = min(max(row.chainage, start), end)
        keep.append(row.Index)
    return points.loc[keep]


def result_points_to_pixml(res1d_file: str, points_file: str, output_xml: str, quantities=None) -> None:
    """Interpolate the reach results at each result point and write them to PI-XML."""
    quantities = quantities or dict(DEFAULT_QUANTITIES)
    points = read_points_file(points_file)
    logger.info(f"Opening {res1d_file}")
    res = Res1D(res1d_file)
    points = _valid_points(res, points)

    root = new_pi_timeseries_root()
    for quantity, (parameter_id, units) in quantities.items():
        queries = [QueryDataReach(quantity, p.river, float(p.chainage)) for p in points.itertuples()]
        if not queries:
            logger.warning(f"No {quantity} results written")
            continue
        df = res.read(queries)  # one read for all points; columns follow the query order
        if df.shape[1] != len(queries):
            raise RuntimeError(f"{quantity}: expected {len(queries)} columns, got {df.shape[1]}")
        table = pd.DataFrame(df.values, index=df.index, columns=list(points["location_id"]))
        add_xml_series(root, table, parameter_id=parameter_id, units=units)
        logger.info(f"{quantity} -> {parameter_id} at {len(queries)} point(s)")
    write_pi_xml(root, output_xml)
    logger.info(f"Written: {output_xml}")
