# fews-mike-adapter

Delft-FEWS General Adapter for MIKE+ models (MIKE 1D HD + NAM).

One command runs the whole forecast chain (every step whose section is present in `settings.ini`):

1. **prepare_dfs0** – FEWS PI-XML forcing (`forcing.xml`) → one DFS0 per parameter
2. **run_mike** – sets the simulation period (from the DFS0 files) and hot/cold start in the
   MIKE+ `.sqlite` project, runs `DHI.MIKEPlus.EngineShell.exe`, copies the result states.
   Optionally also:
   - writes the observed water levels for **data assimilation** (one DFS0 per station), and
   - sets the data-assimilation **time of forecast** to the FEWS forecast time (`time0` from the PI run file)
3. **mikenam_to_pixml** – NAM catchment runoff (`res1d`) → PI-XML (`Q.sim`)
4. **result_points_to_pixml** – HD water level and discharge at result points (river + chainage,
   interpolated along the reach) → PI-XML (`H.sim`, `Q.sim`). The points (and their FEWS
   location ids) come from a CSV that FEWS exports from its MIKE result points location set

## Installation

Install once into a dedicated virtual environment, outside the model folder
(the model folder then only holds `settings.ini` and the MIKE+ model):

```bat
cd <REGION_HOME>\Modules\python
python -m venv mike_adapter_env
mike_adapter_env\Scripts\python.exe -m pip install "git+https://github.com/lokhorstivar/FewsMikeAdapter.git"
```

This creates the executable `mike_adapter_env\Scripts\run_mike_adapter.exe`.

A specific version (git tag) or branch:

```bat
mike_adapter_env\Scripts\python.exe -m pip install "git+https://github.com/lokhorstivar/FewsMikeAdapter.git@v0.1.0"
```

Update to the latest version:

```bat
mike_adapter_env\Scripts\python.exe -m pip install --upgrade --force-reinstall "git+https://github.com/lokhorstivar/FewsMikeAdapter.git"
```

For a private repository use `git+https://<token>@github.com/...`, or `git+ssh://git@github.com/...`.
Git must be installed on the machine.

## Usage

Run from the model folder (the folder containing `settings.ini`):

```bat
run_mike_adapter --forecast
run_mike_adapter --prepare_dfs0 --run_mike
run_mike_adapter --forecast D:\models\Assam\settings.ini
python -m fews_mike_adapter --forecast
```

Without a settings argument, `settings.ini` in the current working directory is used.
`fews-mike-adapter` is installed as an alias of `run_mike_adapter`.

| Flag | Step |
|---|---|
| `--prepare_dfs0` | PI-XML → DFS0 |
| `--run_mike` | update project, run MIKE+, copy states |
| `--mikenam_to_pixml` | NAM results → PI-XML |
| `--result_points_to_pixml` | HD results at result points → PI-XML |
| `--forecast` | all steps configured in `settings.ini` |
| `--debug` | verbose logging |

The exit code is 0 on success and 1 on any error, so FEWS marks the run as failed.

## settings.ini

See [`examples/settings.ini`](examples/settings.ini). **Relative paths are resolved against the
folder of `settings.ini`**, so the adapter works independently of the working directory.
`mikeplus_exe` may be an absolute path, a path relative to `settings.ini`, or a name on `PATH`.

### Cold start

If the state input folder contains files prefixed `Cold_` (exported by FEWS as cold state),
the prefix is removed and the project is set to start from `coldstart_date_time`.
Otherwise a warm start from the exported hot-start files is configured.

### Data assimilation (MIKE+ DA module)

Add a `[da_observations]` section and `run_info_file` in `[run_mike]`:

- FEWS exports the observed water levels (`H.obs`) of the DA stations to a separate PI-XML file
  (not the forcing file). The adapter writes `<locationId>.dfs0` per station (item name
  `Water Level`) for the full simulation period at a regular time step. Missing observations stay
  missing (single gaps are interpolated), so DA simply does not update there. Every location in
  the PI-XML gets a file; the project decides which ones it uses. Optional `locations` (comma
  separated) forces a file for stations FEWS did not export.
- Point each DA station in the MIKE+ project (`mrm_DAUpdatePara.filename`) to that file.
- FEWS exports a PI run file (`exportRunFileActivity`); its `time0` is written to
  `mrm_DAGeneralPara.tof` (time of forecast) before every run.
- A DA station whose observation file has no values, or whose file in `output_folder` was not
  written at all, is switched off for that run (MIKE+ stops otherwise); data assimilation as a whole is switched off when no station has data.
- `data_assimilation = true/false` in `[run_mike]` switches data assimilation on or off
  (`msm_Project.enable_da`). DA needs the MIKE 1D DA licence (`MIKE1DDA`).

### State time

By default FEWS stores an imported state at the end of the run. Put `{time0}` in the
`administrated_*_state` file names (filled with T0 as `yyyyMMdd_HHmmss`, from `run_info_file`)
and let FEWS read the time from the name, so the state is stored at T0:

```xml
<importStateActivity>
	<stateImportDir>%ROOT_DIR%/Assam/OutputStates</stateImportDir>
	<stateFileDateTimePattern>'nam_state_'yyyyMMdd_HHmmss'.res1d'</stateFileDateTimePattern>
	<relativeExportFile>nam_state.res1d</relativeExportFile>
	<stateFileDateTimePattern>'state_1d_'yyyyMMdd_HHmmss'.res1d'</stateFileDateTimePattern>
	<relativeExportFile>state_1d.res1d</relativeExportFile>
</importStateActivity>
```

The state file is the whole result file of the previous run; on a warm start MIKE takes the
time step at the new simulation start from it, and the adapter checks that this time is in the file.

The adapter fails the FEWS run when the MIKE 1D engine reports "Simulation Failed", also when
the engine shell returns exit code 0, and copies the engine's ERROR lines into the log.

### Result points

`points_file` is a CSV with the columns `location_id,river,chainage` (other columns are ignored,
comma or semicolon separated). Let FEWS write it from the location set, so the points are
defined in one place (the map layer file):

```xml
<exportLocationAttributesCsvActivity>
	<exportFile>mike_result_points.csv</exportFile>
	<locationSetId>MIKE_ResultPoints</locationSetId>
	<locationIdColumn columnName="location_id"/>
	<attributeColumn columnName="river" attributeId="River"/>
	<attributeColumn columnName="chainage" attributeId="Chainage"/>
</exportLocationAttributesCsvActivity>
```

```csv
location_id,river,chainage
MIKE_Dibrugarh,Brahmaputra,1848862.434
Brahmaputra_1853576,Brahmaputra,1853576.2
```

All points are read in one go, so hundreds of points are fine. Points with an unknown river or a
chainage outside the reach are logged and skipped.

`quantities` (optional) maps MIKE quantities to FEWS parameters and units, default
`WaterLevel=H.sim:m, Discharge=Q.sim:m3/s`.

## FEWS configuration

Define the executable once in `global.properties`:

```properties
MIKE_ADAPTER_EXE=%REGION_HOME%/Modules/python/mike_adapter_env/Scripts/run_mike_adapter.exe
```

In `ModuleConfigFiles/.../run_mike_forecast.xml` (General Adapter, `workDir` = model folder):

```xml
<executeActivity>
    <command>
        <executable>$MIKE_ADAPTER_EXE$</executable>
    </command>
    <arguments>
        <argument>--forecast</argument>
    </arguments>
    <timeOut>1200000</timeOut>
</executeActivity>
```

See [`examples/run_mike_forecast_executeActivity.xml`](examples/run_mike_forecast_executeActivity.xml).

## Python API

```python
from fews_mike_adapter import (
    pixml_to_dfs0, run_mike_project, mikenam_to_pixml, result_points_to_pixml, write_da_observations
)
```

## Development

```bat
python -m pip install -e .[dev]
pytest
```
