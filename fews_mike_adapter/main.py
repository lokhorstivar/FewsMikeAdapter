import argparse
import logging
import sys

from config import read_settings
from mike11_to_pixml import mike11_to_pixml
from mikenam_to_pixml import mikenam_to_pixml
from pixml_to_dfs0 import pixml_to_dfs0
from run_mike import run_mike_project


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():

    parser = argparse.ArgumentParser(description="MIKE FEWS Adapter Runner")

    parser.add_argument("--prepare_dfs0", action="store_true")
    parser.add_argument("--run_mike", action="store_true")
    parser.add_argument("--mike11_to_pixml", action="store_true")
    parser.add_argument("--mikenam_to_pixml", action="store_true")
    parser.add_argument("--forecast", action="store_true")
    parser.add_argument(
        "settings",
        help="Path to settings.ini",
    )

    args = parser.parse_args()
    if args.forecast:
        args.prepare_dfs0 = True
        args.run_mike = True
        args.mike11_to_pixml = True
        args.mikenam_to_pixml = True
    setup_logging()

    config = read_settings(args.settings)

    #
    # PIXML -> DFS0
    #

    if args.prepare_dfs0:

        if "pixml_to_dfs0" not in config:
            logging.error("Missing [pixml_to_dfs0] section in settings")
        else:

            sec = config["pixml_to_dfs0"]

            pixml_to_dfs0(
                pixml_file=sec.get("pixml_file"),
                output_folder=sec.get("output_folder"),
            )

    #
    # Run MIKE+
    #

    if args.run_mike:

        if "run_mike" not in config:
            logging.error("Missing [run_mike] section in settings")
        else:

            sec = config["run_mike"]

            states = {}

            if "states" in config and config["states"].getboolean(
                "enabled",
                fallback=False,
            ):
                states = config["states"]

            run_mike_project(
                sqlite_file=sec.get("sqlite_file"),
                rainfall_dfs0=sec.get("rainfall_dfs0"),
                temperature_dfs0=sec.get("temperature_dfs0"),
                evaporation_dfs0=sec.get("evaporation_dfs0"),
                mikeplus_exe=sec.get("mikeplus_exe"),
                forecast_buffer_days=sec.getint(
                    "forecast_buffer_days",
                    fallback=0,
                ),
                state_input_folder=states.get("state_input_folder"),
                coldstart_date_time=states.get("coldstart_date_time"),
                output_nam_state=states.get("output_nam_state"),
                administrated_nam_state=states.get("administrated_nam_state"),
                output_hd_state=states.get("output_hd_state"),
                administrated_hd_state=states.get("administrated_hd_state"),
            )

    #
    # MIKE11 -> PIXML
    #

    if args.mike11_to_pixml:

        if "mike11_to_pixml" not in config:
            logging.error("Missing [mike11_to_pixml] section in settings")
        else:

            sec = config["mike11_to_pixml"]

            mike11_to_pixml(
                res1d_file=sec.get("res1d_file"),
                output_xml=sec.get("output_xml"),
            )

    #
    # MIKE NAM -> PIXML
    #

    if args.mikenam_to_pixml:

        if "mikenam_to_pixml" not in config:
            logging.error("Missing [mikenam_to_pixml] section in settings")
        else:

            sec = config["mikenam_to_pixml"]

            mikenam_to_pixml(
                res1d_file=sec.get("res1d_file"),
                output_xml=sec.get("output_xml"),
            )


if __name__ == "__main__":
    main()
