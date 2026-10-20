"""Convert MIKE NAM (rainfall-runoff) results to FEWS PI-XML."""

import logging

from .utils import add_xml_series, new_pi_timeseries_root, write_pi_xml

logger = logging.getLogger(__name__)


def mikenam_to_pixml(
    res1d_file: str,
    output_xml: str,
    parameter_id: str = "Q.sim",
    units: str = "m3/s",
    dva_type: str = "instantaneous",
) -> None:
    """Write the catchment TotalRunOff of a NAM res1d file to PI-XML."""
    from mikeio1d import Res1D

    logger.info(f"Opening {res1d_file}")
    res = Res1D(res1d_file)
    logger.info("Reading catchment runoff...")
    df = res.catchments.TotalRunOff.read()
    logger.debug("Runoff table:\n%s", df)

    root = new_pi_timeseries_root()
    add_xml_series(root, df, parameter_id=parameter_id, units=units, series_type=dva_type)
    write_pi_xml(root, output_xml)
    logger.info(f"Written: {output_xml}")
