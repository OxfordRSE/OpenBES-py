# Agent Context for OpenBES-py Climate Simulation Refactoring

## Project Overview

OpenBES-py is a building energy simulation framework in Python that models hourly energy use based on building
specifications.

## Key Facts

- **Testing Framework**: unittest (NOT pytest)
- **File Organization**: `/src/openbes/simulations/` contains simulation modules
- **Main Entry Point**: `BuildingEnergySimulation` class in `building_energy.py`
- **Performance Bottleneck**: Climate simulation (`climate.py`) - hour-by-hour iterative calculations

## Simulation Dependency Hierarchy

```
Level 0 (Independent):
  - Geometry: depends only on spec dimensions/properties
  - Occupancy: depends on spec + geometry
  - Lighting: depends on spec + occupancy
  - Ventilation: depends on spec + geometry + occupancy
  - Hot Water: depends only on spec
  - Solar Irradiation: depends only on EPW data

Level 1 (Expensive - Hour-by-hour):
  - Climate: depends on geometry + occupancy + lighting + ventilation + spec + EPW data
  - **NOTE**: Climate has iterative dependencies (current hour depends on previous hour's thermal mass)

Level 2 (Depends on Climate):
  - Heating: depends on climate + geometry + occupancy + lighting + ventilation + spec
  - Cooling: depends on climate + geometry + occupancy + lighting + ventilation + spec

Level 3 (Reports):
  - Reports/Retrofit suggestions: depend on all above
```

## The Refactoring Task

### Objective

Allow updating building specifications without rerunning the expensive hour-by-hour climate simulation when
climate-independent specs change (e.g., heating system type, lighting control).

### Three Components to Implement

#### 1. `specs_require_climate_rerun(old_spec, new_spec) -> bool`

- Returns `True` if climate must be recalculated
- Checks if any climate-affecting specs changed
- Climate is affected by:
    - `meteorological_file` (EPW location)
    - Geometry specs (building dimensions, window areas, heat capacity)
    - Occupancy specs (schedules, occupancy ratios)
    - Lighting specs (internal heat gains)
    - Ventilation specs (air supply rates)
    - Climate parameters (infiltration, setpoints, thermal bridges)

#### 2. `reset_climate_cache(climate_sim) -> None`

- Clears intermediate cache (`_populate_cache()` results)
- Clears lazily-computed properties that can be recomputed
- **PRESERVES**: `_hours` DataFrame with expensive hour-by-hour calculations
- Used when dependent simulations change but climate doesn't

#### 3. `BuildingEnergySimulation.update_spec(new_spec) -> None`

- Takes new OpenBESSpecification
- Calls `specs_require_climate_rerun()` to decide path
- **If climate rerun needed**: Recreate climate + all dependencies from scratch
- **If climate unchanged**: Call `reset_climate_cache()`, update dependencies in place
- Always recreate: heating, cooling, ventilation, lighting, occupancy, hot_water
- Clear cached reports (_outputs, _retrofit_report, _full_case_report, _timestamp)

## Implementation Status

### Completed

- ✅ `specs_require_climate_rerun()` function in `climate.py`
    - Comprehensive checks for all climate-affecting specs
    - Handles both top-level and nested parameters

- ✅ `reset_climate_cache()` function in `climate.py`
    - Clears _cache, lazily-computed properties
    - Preserves _hours DataFrame with results

- ✅ `update_spec()` method in `BuildingEnergySimulation`
    - Intelligent routing based on climate rerun check
    - Proper cascade of simulation updates
    - Cache invalidation for reports

- ✅ Import statements updated in `building_energy.py`

### Testing Approach

- Use `unittest` framework
- Test cases should verify:
    1. Spec comparison detects climate changes correctly
    2. Spec comparison ignores non-climate changes
    3. Cache reset preserves _hours DataFrame
    4. update_spec with climate change recreates everything
    5. update_spec without climate change preserves _hours values

## Code Locations

- Climate functions: `/src/openbes/simulations/climate.py` (lines ~1310-1484)
- update_spec method: `/src/openbes/simulations/building_energy.py` (lines ~1313-1413)
- Imports: `/src/openbes/simulations/building_energy.py` (line 14)

## Important Notes

- Do NOT create report.md files or write md files to console - show results in-chat or with in-memory files
- Climate calculation is expensive (~seconds per run)
- The _hours DataFrame is the "value" - preserving it avoids recomputation
- Always reset cached outputs after spec updates
- Error handling should be conservative - fail fast on unexpected state changes

