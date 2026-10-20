"""Prepare and run a MIKE+ project (simulation period, hot/cold start, states)."""

import logging
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def determine_simulation_period(dfs0_files, forecast_buffer_days=0):
    """Return (start, end): the period covered by all given DFS0 files."""
    import mikeio

    starts, ends = [], []
    for dfs0 in dfs0_files:
        if not dfs0:
            continue
        logger.info(f"Reading DFS0: {dfs0}")
        ds = mikeio.read(dfs0)
        logger.info(f"Period found: {ds.time[0]} -> {ds.time[-1]}")
        starts.append(ds.time[0])
        ends.append(ds.time[-1])

    if not starts:
        raise ValueError("No DFS0 files given to determine the simulation period")

    start_time, end_time = max(starts), min(ends)
    logger.info(f"Simulation period: {start_time} -> {end_time}")

    if forecast_buffer_days:
        end_time = end_time + pd.Timedelta(days=forecast_buffer_days)
        logger.info(f"Applied forecast buffer of {forecast_buffer_days} day(s)")
        logger.info(f"New end time: {end_time}")

    return start_time, end_time


def prepare_states(state_input_folder):
    """Detect a cold start (files prefixed ``Cold_``) and strip the prefix.

    Returns True for a cold start, False for a warm start.
    """
    logger.info(f"Checking state folder: {state_input_folder}")
    if not os.path.isdir(state_input_folder):
        logger.warning(f"State input folder not found: {state_input_folder}")
        return False

    cold_files = [f for f in Path(state_input_folder).iterdir() if f.name.startswith("Cold_")]
    if not cold_files:
        logger.info("Warm start detected.")
        return False

    logger.info("Cold start detected.")
    for f in cold_files:
        new_file = f.with_name(f.name.removeprefix("Cold_"))
        logger.info(f"Renaming state file {f.name} -> {new_file.name}")
        f.replace(new_file)
    return True


def update_project(sqlite_file, start_time, end_time, cold_start=None, coldstart_date_time=None):
    """Write the simulation period and hot/cold start settings into the MIKE+ sqlite project.

    ``cold_start=None`` leaves the start settings untouched (no state handling).
    """
    logger.info(f"Opening SQLite project: {sqlite_file}")
    if not os.path.isfile(sqlite_file):
        raise FileNotFoundError(f"MIKE+ project not found: {sqlite_file}")

    conn = sqlite3.connect(sqlite_file)
    try:
        logger.info("Updating simulation period in msm_Project")
        conn.execute(
            "UPDATE msm_Project SET computationbegin=?, computationend=?",
            (
                start_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        if cold_start is True:
            logger.info("Configuring cold start.")
            conn.execute(
                "UPDATE msm_Project SET rdihotstarttimeuseno=0, rdihotstarttime=?",
                (coldstart_date_time,),
            )
            conn.execute(
                "UPDATE msm_HDInitialConditionHotstartFile SET usestarttimeno=0, datetime=?",
                (coldstart_date_time,),
            )
            logger.info(f"Cold start date set to {coldstart_date_time}")
        elif cold_start is False:
            logger.info("Configuring warm start.")
            conn.execute("UPDATE msm_Project SET rdihotstarttimeuseno=1")
            conn.execute("UPDATE msm_HDInitialConditionHotstartFile SET usestarttimeno=1")

        conn.commit()
    finally:
        conn.close()
    logger.info("SQLite updates completed.")


def run_engine(mikeplus_exe, sqlite_file):
    """Run the MIKE+ engine shell on the project; raise on a non-zero exit code."""
    logger.info("Starting MIKE+ simulation")
    logger.info(f"Executable: {mikeplus_exe}")
    logger.info(f"Project: {sqlite_file}")

    result = subprocess.run([str(mikeplus_exe), "-r", str(sqlite_file)])
    logger.info(f"MIKE+ finished with exit code {result.returncode}")
    if result.returncode != 0:
        logger.error("MIKE+ simulation failed.")
        raise RuntimeError(f"MIKE+ run failed (exit code {result.returncode})")


def copy_state(source, target, label):
    """Copy a state file produced by MIKE+ to the folder FEWS imports states from."""
    if not (source and target):
        return
    logger.info(f"Copying {label} state:\n  {source}\n  ->\n  {target}")
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    shutil.copy2(source, target)


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
    """Full MIKE+ step: period from the forcing, states, sqlite update, run, copy states."""
    logger.info("Starting MIKE+ workflow")

    start_time, end_time = determine_simulation_period(
        [rainfall_dfs0, temperature_dfs0, evaporation_dfs0], forecast_buffer_days
    )

    cold_start = prepare_states(state_input_folder) if state_input_folder else None

    update_project(sqlite_file, start_time, end_time, cold_start, coldstart_date_time)
    run_engine(mikeplus_exe, sqlite_file)

    copy_state(output_nam_state, administrated_nam_state, "NAM")
    copy_state(output_hd_state, administrated_hd_state, "HD")

    logger.info("MIKE+ workflow completed successfully.")
