import os
import shutil
import sqlite3
import time

import mikeio
import pandas as pd
import pytest

from fews_mike_adapter.da_observations import write_da_observations
from fews_mike_adapter.result_points_to_pixml import parse_quantities, read_points_file
from fews_mike_adapter.run_info import read_time0
from fews_mike_adapter.run_mike import (
    check_engine_logs,
    check_warm_states,
    state_target,
    update_da_stations,
    update_project,
)
from fews_mike_adapter.utils import add_xml_series, new_pi_timeseries_root, write_pi_xml


RUN_FILE = """<?xml version="1.0" encoding="UTF-8"?>
<Run xmlns="http://www.wldelft.nl/fews/PI" version="1.8">
    <timeZone>0.0</timeZone>
    <startDateTime date="2026-11-13" time="00:00:00"/>
    <endDateTime date="2026-11-28" time="00:00:00"/>
    <time0 date="2026-11-23" time="06:00:00"/>
    <workDir>.</workDir>
</Run>
"""


def test_read_time0(tmp_path):
    f = tmp_path / "run_info.xml"
    f.write_text(RUN_FILE)
    assert read_time0(str(f)) == pd.Timestamp("2026-11-23 06:00")


def test_update_project_sets_da_time_of_forecast(tmp_path):
    db = tmp_path / "model.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE msm_Project (computationbegin TEXT, computationend TEXT)")
    conn.execute("INSERT INTO msm_Project VALUES ('', '')")
    conn.execute("CREATE TABLE mrm_DAGeneralPara (muid TEXT, tof TEXT)")
    conn.execute("INSERT INTO mrm_DAGeneralPara VALUES ('DAGeneral_1', '2025-09-23 09:30:00')")
    conn.commit()
    conn.close()

    update_project(
        str(db),
        pd.Timestamp("2026-11-13"),
        pd.Timestamp("2026-11-28"),
        da_time_of_forecast=pd.Timestamp("2026-11-23 06:00"),
    )
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT tof FROM mrm_DAGeneralPara").fetchone()[0] == "2026-11-23 06:00:00"
    assert conn.execute("SELECT computationbegin FROM msm_Project").fetchone()[0] == "2026-11-13 00:00:00"


def test_da_observations(tmp_path):
    index = pd.date_range("2026-11-20", periods=4, freq="h")
    df = pd.DataFrame({"4": [100.0, None, 100.2, 100.3]}, index=index)
    root = new_pi_timeseries_root()
    add_xml_series(root, df, parameter_id="H.obs", units="m")
    xml = tmp_path / "obs.xml"
    write_pi_xml(root, str(xml))

    files = write_da_observations(
        str(xml), str(tmp_path / "DA"), "2026-11-19 22:00", "2026-11-20 06:00", locations=["4", "34"]
    )
    assert sorted(f.split("/")[-1].split("\\")[-1] for f in files) == ["34.dfs0", "4.dfs0"]
    ds = mikeio.read(str(tmp_path / "DA" / "4.dfs0"))
    assert ds.items[0].name == "Water Level"
    s = ds[0].to_dataframe().iloc[:, 0]
    assert pd.isna(s.iloc[0])                       # before the first observation: missing
    assert abs(s.loc["2026-11-20 01:00"] - 100.1) < 1e-4  # single gap interpolated
    assert pd.isna(s.iloc[-1])                      # after the last observation: missing
    assert mikeio.read(str(tmp_path / "DA" / "34.dfs0"))[0].to_dataframe().isna().all().all()


def test_points_file_and_quantities(tmp_path):
    f = tmp_path / "points.csv"
    f.write_text("location_id;river;chainage\nMIKE_Dibrugarh;Brahmaputra;1848862.434\nx;;\n")
    g = read_points_file(str(f))
    assert len(g) == 1 and g.loc[0, "location_id"] == "MIKE_Dibrugarh"
    assert g.loc[0, "river"] == "Brahmaputra" and g.loc[0, "chainage"] == 1848862.434
    assert parse_quantities("WaterLevel=H.sim:m") == {"WaterLevel": ("H.sim", "m")}
    assert parse_quantities(None)["Discharge"] == ("Q.sim", "m3/s")


def test_update_da_stations(tmp_path):
    db = tmp_path / "p.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE mrm_DAUpdatePara (muid TEXT, filename TEXT, active INTEGER)")
    c.execute("CREATE TABLE msm_Project (enable_da INTEGER)")
    c.executemany("INSERT INTO mrm_DAUpdatePara VALUES (?,?,?)", [
        ("Dhubri", r"piInputTimeSeries\DA\29.dfs0", 1),
        ("Dibrugarh", r"piInputTimeSeries\DA\4.dfs0", 0),
        ("Pandu", r"Time_Series\Pandu.dfs0", 0),
    ])
    c.execute("INSERT INTO msm_Project VALUES (1)")
    c.commit(); c.close()

    update_da_stations(str(db), {str(tmp_path / "DA" / "29.dfs0"): 0, str(tmp_path / "DA" / "4.dfs0"): 12})
    c = sqlite3.connect(db)
    assert dict(c.execute("SELECT muid, active FROM mrm_DAUpdatePara")) == {"Dhubri": 0, "Dibrugarh": 1, "Pandu": 0}
    assert c.execute("SELECT enable_da FROM msm_Project").fetchone()[0] == 1
    c.close()

    update_da_stations(str(db), {"29.dfs0": 0, "4.dfs0": 0})
    c = sqlite3.connect(db)
    assert c.execute("SELECT enable_da FROM msm_Project").fetchone()[0] == 0


def test_check_engine_logs(tmp_path):
    db = tmp_path / "Proj.sqlite"
    db.write_text("")
    t = time.time() - 1
    (tmp_path / "Proj_Sim_1._spi_").write_text("MESSAG Running\nMESSAG Simulation Failed\n")
    (tmp_path / "Proj_Sim_1.log").write_text("x: ERROR: License module 'MIKE1DDA' not found.\nok\n")
    with pytest.raises(RuntimeError, match="MIKE1DDA"):
        check_engine_logs(str(db), t)
    (tmp_path / "Proj_Sim_1._spi_").write_text("MESSAG Simulation finished\n")
    check_engine_logs(str(db), t)  # no exception


def test_check_warm_states(tmp_path):
    src = "/mnt/user-data/uploads/Downloads/Brahmaputra_1D_Model/Brahmaputra_1D_Model/" \
          "Brahmaputra_Jaxa_Survey_m1d - Result Files/Brahmaputra_1BaseDefault_Network_HD.res1d"
    if not os.path.isfile(src):
        pytest.skip("model results not available")
    shutil.copy(src, tmp_path / "state_1d.res1d")
    check_warm_states(str(tmp_path), "2025-09-20 08:30")
    with pytest.raises(RuntimeError, match="cold state"):
        check_warm_states(str(tmp_path), "2026-07-12 15:00")


def test_update_da_stations_missing_file(tmp_path):
    db = tmp_path / "p.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE mrm_DAUpdatePara (muid TEXT, filename TEXT, active INTEGER)")
    c.execute("CREATE TABLE msm_Project (enable_da INTEGER)")
    c.executemany("INSERT INTO mrm_DAUpdatePara VALUES (?,?,?)", [
        ("Dhubri", r"piInputTimeSeries\DA\29.dfs0", 1),      # in DA folder, no file written
        ("Dibrugarh", r"piInputTimeSeries\DA\4.dfs0", 1),
        ("Other", r"Time_Series\Other.dfs0", 1),             # elsewhere: untouched
    ])
    c.execute("INSERT INTO msm_Project VALUES (1)")
    c.commit(); c.close()
    da = tmp_path / "piInputTimeSeries" / "DA"
    update_da_stations(str(db), {str(da / "4.dfs0"): 5}, str(da))
    c = sqlite3.connect(db)
    assert dict(c.execute("SELECT muid, active FROM mrm_DAUpdatePara")) == {"Dhubri": 0, "Dibrugarh": 1, "Other": 1}


def test_state_target():
    assert state_target("OutputStates/state_1d_{time0}.res1d", "2026-07-22 15:00") == "OutputStates/state_1d_20260722_150000.res1d"
    assert state_target("OutputStates/state_1d.res1d", None) == "OutputStates/state_1d.res1d"
    with pytest.raises(ValueError):
        state_target("x_{time0}.res1d", None)
