"""Prepare and run a MIKE+ project (simulation period, hot/cold start, states)."""

import logging
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import mikeio
import pandas as pd
from mikeio1d import Res1D

from .da_observations import write_da_observations
from .run_info import read_time0

logger = logging.getLogger(__name__)


def determine_simulation_period(dfs0_files, forecast_buffer_days=0):
    """Return (start, end): the period covered by all given DFS0 files."""
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


def check_warm_states(state_input_folder, start_time):
    """Raise when a warm state file does not contain the simulation start time.

    A warm start takes the state at the simulation start from the previous run's res1d file.
    A state from a failed or short run does not cover that time and MIKE stops with
    "Index was outside the bounds of the array"; this gives a clear message instead.
    """
    start = pd.Timestamp(start_time)
    for f in sorted(Path(state_input_folder).glob("*.res1d")):
        times = Res1D(str(f)).time_index
        first, last = pd.Timestamp(times[0]), pd.Timestamp(times[-1])
        logger.info(f"Warm state {f.name}: {first} - {last} ({len(times)} time steps)")
        if not (first <= start <= last):
            raise RuntimeError(
                f"Warm state {f.name} covers {first} - {last}, but the simulation starts at {start}. "
                "The state probably comes from a failed run: run once with a cold state "
                "(or delete that state in FEWS)."
            )


def update_project(
    sqlite_file,
    start_time,
    end_time,
    cold_start=None,
    coldstart_date_time=None,
    da_time_of_forecast=None,
):
    """Write the simulation period and hot/cold start settings into the MIKE+ sqlite project.

    ``cold_start=None`` leaves the start settings untouched (no state handling).
    ``da_time_of_forecast`` (optional) sets the time of forecast of the data assimilation:
    observations up to this time are assimilated, after it the error forecast is used.
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

        if da_time_of_forecast is not None:
            tof = pd.Timestamp(da_time_of_forecast).strftime("%Y-%m-%d %H:%M:%S")
            try:
                n = conn.execute("UPDATE mrm_DAGeneralPara SET tof=?", (tof,)).rowcount
            except sqlite3.OperationalError:
                n = 0
            if n:
                logger.info(f"Data assimilation time of forecast set to {tof}")
            else:
                logger.warning("No data assimilation settings found; time of forecast not set")

        conn.commit()
    finally:
        conn.close()
    logger.info("SQLite updates completed.")


def update_da_stations(sqlite_file, da_files, da_folder=None):
    """Switch DA stations on or off depending on whether their observation file has data.

    MIKE+ stops with "does not contain valid values" when an active DA station has an
    observation file without any value. ``da_files`` is {dfs0 file: number of valid values}
    as returned by ``write_da_observations``. Only stations whose ``filename`` points to one of
    these files are changed (matched on file name); others keep their setting. A station whose
    file lies in ``da_folder`` but was not written (no data from FEWS) is switched off too. Data
    assimilation as a whole (``msm_Project.enable_da``) is switched off when no station is left.
    """
    counts = {os.path.basename(str(f)).lower(): n for f, n in da_files.items()}
    conn = sqlite3.connect(sqlite_file)
    try:
        try:
            rows = conn.execute("SELECT muid, filename, active FROM mrm_DAUpdatePara").fetchall()
        except sqlite3.OperationalError:
            logger.warning("No data assimilation stations (mrm_DAUpdatePara) in the project")
            return
        managed = 0
        for muid, filename, active in rows:
            rel = str(filename or "").replace("\\", "/")
            name = os.path.basename(rel).lower()
            if name not in counts:
                full = os.path.normcase(os.path.normpath(os.path.join(os.path.dirname(sqlite_file), rel)))
                in_da_folder = da_folder and os.path.dirname(full) == os.path.normcase(
                    os.path.normpath(da_folder)
                )
                if in_da_folder and active:
                    managed += 1
                    conn.execute("UPDATE mrm_DAUpdatePara SET active=0 WHERE muid=?", (muid,))
                    logger.warning(f"DA station {muid}: no observations from FEWS ({filename}), switched off for this run")
                continue
            managed += 1
            new = 1 if counts[name] > 0 else 0
            conn.execute("UPDATE mrm_DAUpdatePara SET active=? WHERE muid=?", (new, muid))
            if new == 0:
                logger.warning(f"DA station {muid}: no observations in {filename}, switched off for this run")
            else:
                logger.info(f"DA station {muid}: {counts[name]} observations, active")
        if managed:
            n_active = conn.execute(
                "SELECT COUNT(*) FROM mrm_DAUpdatePara WHERE active=1"
            ).fetchone()[0]
            enable = 1 if n_active else 0
            try:
                conn.execute("UPDATE msm_Project SET enable_da=?", (enable,))
            except sqlite3.OperationalError:
                logger.warning("msm_Project.enable_da not found; data assimilation not switched")
            else:
                if enable:
                    logger.info(f"Data assimilation on ({n_active} active station(s))")
                else:
                    logger.warning("No DA station has observations: data assimilation switched off")
        conn.commit()
    finally:
        conn.close()


def set_data_assimilation(sqlite_file, enabled):
    """Switch data assimilation in the project on or off (``msm_Project.enable_da``)."""
    conn = sqlite3.connect(sqlite_file)
    try:
        conn.execute("UPDATE msm_Project SET enable_da=?", (1 if enabled else 0,))
        conn.commit()
        logger.info(f"Data assimilation {'on' if enabled else 'off'} (settings: data_assimilation)")
    except sqlite3.OperationalError:
        logger.warning("msm_Project.enable_da not found; data assimilation setting ignored")
    finally:
        conn.close()


def check_engine_logs(sqlite_file, since):
    """Raise when the MIKE 1D engine reports a failed simulation.

    The engine shell can return exit code 0 after a failed simulation; the progress file
    (``<project>_<simulation>._spi_``) then contains "Simulation Failed". The ERROR lines of the
    matching ``.log`` file are logged and put in the exception message.
    """
    folder = Path(sqlite_file).parent
    stem = Path(sqlite_file).stem
    failed = []
    for spi in folder.glob(f"{stem}_*._spi_"):
        if spi.stat().st_mtime < since:
            continue
        if "Simulation Failed" not in spi.read_text(errors="replace"):
            continue
        log = spi.with_name(spi.name[: -len("._spi_")] + ".log")
        errors = []
        if log.is_file():
            errors = [l.strip() for l in log.read_text(errors="replace").splitlines() if "ERROR" in l]
        for line in errors:
            logger.error(f"MIKE: {line}")
        failed.append(f"{log.name}: " + ("; ".join(errors) or "Simulation Failed"))
    if failed:
        raise RuntimeError("MIKE+ simulation failed - " + " | ".join(failed))


def run_engine(mikeplus_exe, sqlite_file):
    """Run the MIKE+ engine shell on the project; raise when the simulation failed."""
    logger.info("Starting MIKE+ simulation")
    logger.info(f"Executable: {mikeplus_exe}")
    logger.info(f"Project: {sqlite_file}")

    started = time.time() - 1
    result = subprocess.run([str(mikeplus_exe), "-r", str(sqlite_file)])
    logger.info(f"MIKE+ finished with exit code {result.returncode}")
    if result.returncode != 0:
        logger.error("MIKE+ simulation failed.")
        raise RuntimeError(f"MIKE+ run failed (exit code {result.returncode})")
    check_engine_logs(sqlite_file, started)


def state_target(target, time0):
    """Fill ``{time0}`` in a state file name with T0 as yyyyMMdd_HHmmss.

    FEWS can take the state time from the file name (``stateFileDateTimePattern`` in the
    importStateActivity), so the state is stored at T0 instead of at the end of the run.
    """
    if not target or "{time0}" not in str(target):
        return target
    if time0 is None:
        raise ValueError(f"State file name {target} contains {{time0}} but no run_info_file is configured")
    return str(target).replace("{time0}", pd.Timestamp(time0).strftime("%Y%m%d_%H%M%S"))


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
    run_info_file=None,
    da_observations=None,
    data_assimilation=None,
):
    """Full MIKE+ step: period from the forcing, states, sqlite update, run, copy states.

    ``run_info_file``: PI run file exported by FEWS; its time0 is used as the time of
    forecast of the data assimilation.
    ``da_observations``: optional dict with the arguments of
    :func:`fews_mike_adapter.da_observations.write_da_observations` (without the period),
    to write the observed water levels used by the data assimilation.
    ``data_assimilation``: True/False switches data assimilation on/off in the project
    (False needs no DA licence); None leaves the project setting as it is.
    """
    logger.info("Starting MIKE+ workflow")

    start_time, end_time = determine_simulation_period(
        [rainfall_dfs0, temperature_dfs0, evaporation_dfs0], forecast_buffer_days
    )

    da_files = None
    if da_observations:
        da_files = write_da_observations(start_time=start_time, end_time=end_time, **da_observations)

    time0 = None
    if run_info_file:
        time0 = read_time0(run_info_file)

    cold_start = prepare_states(state_input_folder) if state_input_folder else None
    if cold_start is False and os.path.isdir(state_input_folder):
        check_warm_states(state_input_folder, start_time)

    update_project(
        sqlite_file, start_time, end_time, cold_start, coldstart_date_time, da_time_of_forecast=time0
    )
    if data_assimilation is not None:
        set_data_assimilation(sqlite_file, data_assimilation)
    if da_files is not None and data_assimilation is not False:
        update_da_stations(sqlite_file, da_files, da_observations.get("output_folder"))
    run_engine(mikeplus_exe, sqlite_file)

    copy_state(output_nam_state, state_target(administrated_nam_state, time0), "NAM")
    copy_state(output_hd_state, state_target(administrated_hd_state, time0), "HD")

    logger.info("MIKE+ workflow completed successfully.")
