"""Command line interface, called from the Delft-FEWS General Adapter.

Examples::

    run_mike_adapter --forecast                  (uses settings.ini in the current folder)
    run_mike_adapter --forecast path/to/settings.ini
    run_mike_adapter --prepare_dfs0 --run_mike
    run_mike_adapter --result_points_to_pixml
    python -m fews_mike_adapter --forecast

``--forecast`` runs every step whose section is present in settings.ini.

Relative paths in settings.ini are resolved against the folder of settings.ini.
"""

import argparse
import logging
import sys

from . import __version__
from .config import read_settings, resolve_executable, resolve_path
from .result_points_to_pixml import parse_quantities, result_points_to_pixml
from .mikenam_to_pixml import mikenam_to_pixml
from .pixml_to_dfs0 import pixml_to_dfs0
from .run_mike import run_mike_project

logger = logging.getLogger("fews_mike_adapter")


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_mike_adapter", description="MIKE+ adapter for Delft-FEWS"
    )
    parser.add_argument("--prepare_dfs0", action="store_true", help="PI-XML forcing -> DFS0")
    parser.add_argument("--run_mike", action="store_true", help="update project and run MIKE+")
    parser.add_argument("--mikenam_to_pixml", action="store_true", help="NAM results -> PI-XML")
    parser.add_argument(
        "--result_points_to_pixml",
        action="store_true",
        help="HD results at result points (river/chainage) -> PI-XML",
    )
    parser.add_argument(
        "--forecast", action="store_true", help="all steps configured in settings.ini"
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "settings",
        nargs="?",
        default="settings.ini",
        help="Path to settings.ini (default: settings.ini in the current working directory)",
    )
    return parser


def _section(config, name):
    if name not in config:
        raise KeyError(f"Missing [{name}] section in settings")
    return config[name]


STEPS = ["prepare_dfs0", "run_mike", "mikenam_to_pixml", "result_points_to_pixml"]
SECTIONS = {
    "prepare_dfs0": "pixml_to_dfs0",
    "run_mike": "run_mike",
    "mikenam_to_pixml": "mikenam_to_pixml",
    "result_points_to_pixml": "result_points_to_pixml",
}


def run(args):
    if not args.forecast and not any(getattr(args, step) for step in STEPS):
        raise SystemExit("Nothing to do: give --forecast or one or more step flags")

    config = read_settings(args.settings)
    p = lambda sec, key: resolve_path(config, sec.get(key))  # noqa: E731

    if args.forecast:
        # all steps whose section is present in settings.ini
        for step in STEPS:
            if SECTIONS[step] in config:
                setattr(args, step, True)
        logger.info("Steps: " + ", ".join(s for s in STEPS if getattr(args, s)))

    if args.prepare_dfs0:
        sec = _section(config, "pixml_to_dfs0")
        pixml_to_dfs0(pixml_file=p(sec, "pixml_file"), output_folder=p(sec, "output_folder"))

    if args.run_mike:
        sec = _section(config, "run_mike")
        states = {}
        if "states" in config and config["states"].getboolean("enabled", fallback=False):
            st = config["states"]
            states = {
                "state_input_folder": p(st, "state_input_folder"),
                "coldstart_date_time": st.get("coldstart_date_time"),
                "output_nam_state": p(st, "output_nam_state"),
                "administrated_nam_state": p(st, "administrated_nam_state"),
                "output_hd_state": p(st, "output_hd_state"),
                "administrated_hd_state": p(st, "administrated_hd_state"),
            }
        da_observations = None
        if "da_observations" in config:
            da = config["da_observations"]
            da_observations = {
                "pixml_file": p(da, "pixml_file"),
                "output_folder": p(da, "output_folder"),
                "item_name": da.get("item_name", fallback="Water Level"),
                "timestep": da.get("timestep", fallback="1h"),
                "locations": [x.strip() for x in da.get("locations", fallback="").split(",") if x.strip()],
            }
        run_mike_project(
            sqlite_file=p(sec, "sqlite_file"),
            rainfall_dfs0=p(sec, "rainfall_dfs0"),
            temperature_dfs0=p(sec, "temperature_dfs0"),
            evaporation_dfs0=p(sec, "evaporation_dfs0"),
            mikeplus_exe=resolve_executable(config, sec.get("mikeplus_exe")),
            forecast_buffer_days=sec.getint("forecast_buffer_days", fallback=0),
            run_info_file=p(sec, "run_info_file"),
            da_observations=da_observations,
            data_assimilation=sec.getboolean("data_assimilation", fallback=None),
            **states,
        )

    if args.mikenam_to_pixml:
        sec = _section(config, "mikenam_to_pixml")
        mikenam_to_pixml(res1d_file=p(sec, "res1d_file"), output_xml=p(sec, "output_xml"))

    if args.result_points_to_pixml:
        sec = _section(config, "result_points_to_pixml")
        result_points_to_pixml(
            res1d_file=p(sec, "res1d_file"),
            points_file=p(sec, "points_file"),
            output_xml=p(sec, "output_xml"),
            quantities=parse_quantities(sec.get("quantities")),
        )


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if args.debug else logging.INFO)
    try:
        run(args)
    except Exception:
        logger.exception("run_mike_adapter failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
