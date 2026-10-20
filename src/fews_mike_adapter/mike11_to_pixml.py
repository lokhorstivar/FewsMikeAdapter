"""Convert MIKE 1D (HD) results to FEWS PI-XML."""

import logging

from .utils import add_xml_series, new_pi_timeseries_root, write_pi_xml

logger = logging.getLogger(__name__)


def mike11_to_pixml(
    res1d_file: str,
    output_xml: str,
    parameter_id: str = "H.sim",
    units: str = "m",
) -> None:
    """Write the node water levels of a MIKE 1D res1d file to PI-XML."""
    from mikeio1d import Res1D

    logger.info(f"Opening {res1d_file}")
    res = Res1D(res1d_file)
    logger.info("Reading water levels...")
    wl_df = res.nodes.WaterLevel.read()

    root = new_pi_timeseries_root()
    add_xml_series(root, wl_df, parameter_id=parameter_id, units=units)
    write_pi_xml(root, output_xml)
    logger.info(f"Written: {output_xml}")
