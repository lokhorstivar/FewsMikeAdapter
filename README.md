# FewsMikeAdapter
Adapter to start a Mike+ (mike nam + mike11) simulation from fews. The adapter focusses on 4 key steps
- Convert fews pixml timeseries to dfs0 files for forcings
- Run Mike+ model including state management
- Convert Mike11 outcomes to pixml for FEWS ingestion
- Convert MikeNam outcomes to pixml for FEWS ingestion

The adapter works by calling `main.py` followed by multiple arguments. First of all which functions to execute. You can chose from:
- --prepare_dfs0
- --run_mike
- --mikenam_to_pixml
- --mike11_to_pixml
- --forecast

The first four functions will call a part of the workflow, the `--forecast` flag runs all modules consequtively. To provide the adapter with the required information a `settings.ini` should be provided. The full comment then looks like this: `python main.py --forecast settings.ini`. An example of the settings.ini is provided in example_config_files.

prepare_dfs0
=============
The prepare_dfs0 function takes a FEWS PIXML file as input and turns this into one or multiple dfs0 files. Every unique parameter will be placed in its own dfs0 file. So, for example, if the PIXML contains precipitation and evaporation data, it will be converted into precipitation.dfs0 and evaporation.dfs0. The Mike+ model should be configured to direct to the output files of this function. So if the function creates `input\precipitation.dfs0`, the mike timeseries should be mapped to this file. To ensure the file can be used, the timeseries/basin id's should be the same. The method has only been tested for catchment timeseries which are the boundary conditions for the NAM model. In Delft-FEWS you create basin averaged forcing timeseries for the same basins that are used in the Mike+ model.

run_mike
==========
The run_mike function handles states and executes the actual mike+ simulation. To be able to run this function, all input files (forcings etc.) should be in place and only the state configuration may be updated (optional). In the ini, point to the Mike+ executable and the model sqlite. The adapter assumes that temperature, evaporation and precipitation are all provided as forcings. It will check these three dfs0 files to set the start and end date of the simulation based on available timeseries. 

If states are included there are two different options:
1. A warm state was exported. In this case, the module will configure the simulation to look up the time0 in the simulation in the state file and take that conditions as the initial conditions. 
2. A cold state was exported. For the adapter to know that it is dealing with a cold state, the states should be stored as `Cold_`+state name in the coldstates folder of Fews. The precise naming is important because the adapter uses the `Cold_` prefix to recognize it has to run a different workflow. If a cold state is used, the simulation likely cannot look up its actual t0 in the cold state file. Therefore, a specific date has to be prescribed and Mike will take the hydraulic and hydrological conditions at that moment as its initial state.

After the simulation is finished, the states will be moved to the outputstates folder which Delft-FEWS can utilize to ingest the states. Please note that the hydraulic results and the RDII catchment results should be prepared for archiving (not the regular catchment results).

mikenam_to_pixml
=================
mikenam_to_pixml converts the hydraulic (1d) outcome of the model into a PIXML file to be ingested into delft-fews. 

mike11_to_pixml
=================
mike11_to_pixml converts the hydrological outcome of the model into a PIXML file to be ingested into delft-fews. 