# fews-mike-adapter

Delft-FEWS General Adapter for MIKE+ models (MIKE 1D HD + NAM).

One command runs the whole forecast chain:

1. **prepare_dfs0** – FEWS PI-XML forcing (`forcing.xml`) → one DFS0 per parameter
2. **run_mike** – sets the simulation period (from the DFS0 files) and hot/cold start in the
   MIKE+ `.sqlite` project, runs `DHI.MIKEPlus.EngineShell.exe`, copies the result states
3. **mike11_to_pixml** – HD node water levels (`res1d`) → PI-XML (`H.sim`)
4. **mikenam_to_pixml** – NAM catchment runoff (`res1d`) → PI-XML (`Q.sim`)

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
| `--mike11_to_pixml` | HD results → PI-XML |
| `--mikenam_to_pixml` | NAM results → PI-XML |
| `--forecast` | all four steps |
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
from fews_mike_adapter import pixml_to_dfs0, run_mike_project, mike11_to_pixml, mikenam_to_pixml
```

## Development

```bat
python -m pip install -e .[dev]
pytest
```
