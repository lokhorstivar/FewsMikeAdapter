import logging
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import mikeio
import pandas as pd


def run_mike_project(
    sqlite_file,
    rainfall_dfs0,
    mikeplus_exe,
    temperature_dfs0=None,
    evaporation_dfs0=None,
    forecast_buffer_days=0,
    state_input_folder=None,
    coldstart_date_time=None,
    output_nam_state=None,
    administrated_nam_state=None,
    output_hd_state=None,
    administrated_hd_state=None,
):

    logging.info("Starting MIKE+ workflow")

    #
    # Determine simulation period
    #
    starts = []
    ends = []

    for dfs0 in [rainfall_dfs0, temperature_dfs0, evaporation_dfs0]:

        if dfs0:

            logging.info(f"Reading DFS0: {dfs0}")

            ds = mikeio.read(dfs0)

            logging.info(f"Period found: {ds.time[0]} -> {ds.time[-1]}")

            starts.append(ds.time[0])
            ends.append(ds.time[-1])

    start_time = max(starts)
    end_time = min(ends)

    logging.info(f"Simulation period: {start_time} -> {end_time}")

    if forecast_buffer_days:

        end_time = end_time + pd.Timedelta(days=forecast_buffer_days)

        logging.info(f"Applied forecast buffer of " f"{forecast_buffer_days} day(s)")

        logging.info(f"New end time: {end_time}")

    #
    # State handling
    #
    cold_files = False

    if state_input_folder:

        logging.info(f"Checking state folder: {state_input_folder}")

        if os.path.isdir(state_input_folder):

            cold_files = any(
                f.startswith("Cold_") for f in os.listdir(state_input_folder)
            )

            if cold_files:

                logging.info("Cold start detected.")

                for f in Path(state_input_folder).iterdir():

                    if f.name.startswith("Cold_"):

                        new_file = f.with_name(f.name.removeprefix("Cold_"))

                        logging.info(
                            f"Renaming state file " f"{f.name} -> {new_file.name}"
                        )

                        f.rename(new_file)

            else:

                logging.info("Warm start detected.")

        else:

            logging.warning(f"State input folder not found: " f"{state_input_folder}")

    #
    # Update MIKE+ project
    #
    logging.info(f"Opening SQLite project: {sqlite_file}")

    conn = sqlite3.connect(sqlite_file)

    logging.info("Updating simulation period in msm_Project")

    conn.execute(
        """
        UPDATE msm_Project
        SET
            computationbegin=?,
            computationend=?
        """,
        (
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    conn.commit()

    if state_input_folder:

        if cold_files:

            logging.info("Configuring cold start.")

            conn.execute(
                """
                UPDATE msm_Project
                SET
                    rdihotstarttimeuseno=0,
                    rdihotstarttime=?
                """,
                (coldstart_date_time,),
            )

            conn.execute(
                """
                UPDATE msm_HDInitialConditionHotstartFile
                SET
                    usestarttimeno = 0,
                    datetime = ?
                """,
                (coldstart_date_time,),
            )

            logging.info(f"Cold start date set to " f"{coldstart_date_time}")

        else:

            logging.info("Configuring warm start.")

            conn.execute(
                """
                UPDATE msm_Project
                SET
                    rdihotstarttimeuseno = 1
                """
            )

            conn.execute(
                """
                UPDATE msm_HDInitialConditionHotstartFile
                SET
                    usestarttimeno = 1
                """
            )

        conn.commit()

    conn.close()

    logging.info("SQLite updates completed.")

    #
    # Run MIKE+
    #
    logging.info("Starting MIKE+ simulation")

    logging.info(f"Executable: {mikeplus_exe}")

    logging.info(f"Project: {sqlite_file}")

    result = subprocess.run(
    [str(mikeplus_exe), "-r", str(sqlite_file)]
    )

    logging.info(
    f"MIKE+ finished with exit code "
    f"{result.returncode}"
    )

    if result.returncode != 0:
        logging.error(
        "MIKE+ simulation failed."
        )

        raise RuntimeError(
        "MIKE+ run failed"
        )

    #
    # Copy states
    #
    if output_nam_state and administrated_nam_state:

        logging.info(
            f"Copying NAM state:\n"
            f"  {output_nam_state}\n"
            f"  ->\n"
            f"  {administrated_nam_state}"
        )

        shutil.copy2(
            output_nam_state,
            administrated_nam_state,
        )

    if output_hd_state and administrated_hd_state:

        logging.info(
            f"Copying HD state:\n"
            f"  {output_hd_state}\n"
            f"  ->\n"
            f"  {administrated_hd_state}"
        )

        shutil.copy2(
            output_hd_state,
            administrated_hd_state,
        )

    logging.info("MIKE+ workflow completed successfully.")
