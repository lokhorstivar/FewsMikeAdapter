"""Command line interface, called from the Delft-FEWS General Adapter.

Examples::

    run_mike_adapter --forecast                  (uses settings.ini in the current folder)
    run_mike_adapter --forecast path/to/settings.ini
    run_mike_adapter --prepare_dfs0 --run_mike
    python -m fews_mike_adapter --forecast

Relative paths in settings.ini are resolved against the folder of settings.ini.
"""

import argparse
import logging
import sys

from . import __version__
from .config import read_settings, resolve_executable, resolve_path
from .mike11_to_pixml import mike11_to_pixml
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
    parser.add_argument("--mike11_to_pixml", action="store_true", help="HD results -> PI-XML")
    parser.add_argument("--mikenam_to_pixml", action="store_true", help="NAM results -> PI-XML")
    parser.add_argument("--forecast", action="store_true", help="all four steps")
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


def run(args):
    if args.forecast:
        args.prepare_dfs0 = args.run_mike = True
        args.mike11_to_pixml = args.mikenam_to_pixml = True

    if not any([args.prepare_dfs0, args.run_mike, args.mike11_to_pixml, args.mikenam_to_pixml]):
        raise SystemExit("Nothing to do: give --forecast or one or more step flags")

    config = read_settings(args.settings)
    p = lambda sec, key: resolve_path(config, sec.get(key))  # noqa: E731

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
        run_mike_project(
            sqlite_file=p(sec, "sqlite_file"),
            rainfall_dfs0=p(sec, "rainfall_dfs0"),
            temperature_dfs0=p(sec, "temperature_dfs0"),
            evaporation_dfs0=p(sec, "evaporation_dfs0"),
            mikeplus_exe=resolve_executable(config, sec.get("mikeplus_exe")),
            forecast_buffer_days=sec.getint("forecast_buffer_days", fallback=0),
            **states,
        )

    if args.mike11_to_pixml:
        sec = _section(config, "mike11_to_pixml")
        mike11_to_pixml(res1d_file=p(sec, "res1d_file"), output_xml=p(sec, "output_xml"))

    if args.mikenam_to_pixml:
        sec = _section(config, "mikenam_to_pixml")
        mikenam_to_pixml(res1d_file=p(sec, "res1d_file"), output_xml=p(sec, "output_xml"))


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
