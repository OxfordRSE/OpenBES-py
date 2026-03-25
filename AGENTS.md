# Agent Context for OpenBES-py Thermal Simulation Refactoring

## Project Overview

OpenBES-py is a building energy simulation framework in Python that models hourly energy use based on building
specifications.

## Key Facts

- **Testing Framework**: unittest (NOT pytest)
- **File Organization**: `/src/openbes/simulations/` contains simulation modules
- **Main Entry Point**: `BuildingEnergySimulation` class in `building_energy.py`
- **Performance Bottleneck**: Thermal simulation (`thermal.py`) - hour-by-hour iterative calculations

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
  - Thermal: depends on geometry + occupancy + lighting + ventilation + spec + EPW data
  - **NOTE**: Thermal has iterative dependencies (current hour depends on previous hour's thermal mass)

Level 2 (Depends on Thermal):
  - Heating: depends on thermal + geometry + occupancy + lighting + ventilation + spec
  - Cooling: depends on thermal + geometry + occupancy + lighting + ventilation + spec

Level 3 (Reports):
  - Reports/Retrofit suggestions: depend on all above
```

## The Refactoring Task

### Objective

Allow updating building specifications without rerunning the expensive hour-by-hour thermal simulation when
thermal-independent specs change (e.g., heating system type, lighting control).

### Three Components to Implement

#### 1. `specs_require_thermal_rerun(old_spec, new_spec) -> bool`

- Returns `True` if thermal must be recalculated
- Checks if any thermal-affecting specs changed
- Thermal is affected by:
    - `meteorological_file` (EPW location)
    - Geometry specs (building dimensions, window areas, heat capacity)
    - Occupancy specs (schedules, occupancy ratios)
    - Lighting specs (internal heat gains)
    - Ventilation specs (air supply rates)
  - Thermal parameters (infiltration, setpoints, thermal bridges)

#### 2. `reset_thermal_cache(thermal_sim) -> None`

- Clears intermediate cache (`_populate_cache()` results)
- Clears lazily-computed properties that can be recomputed
- **PRESERVES**: `_hours` DataFrame with expensive hour-by-hour calculations
- Used when dependent simulations change but thermal doesn't

#### 3. `BuildingEnergySimulation.update_spec(new_spec) -> None`

- Takes new OpenBESSpecification
- Calls `specs_require_thermal_rerun()` to decide path
- **If thermal rerun needed**: Recreate thermal + all dependencies from scratch
- **If thermal unchanged**: Call `reset_thermal_cache()`, update dependencies in place
- Always recreate: heating, cooling, ventilation, lighting, occupancy, hot_water
- Clear cached reports (_outputs, _retrofit_report, _full_case_report, _timestamp)

## Implementation Status

### Completed

- ✅ `specs_require_thermal_rerun()` function in `thermal.py`
  - Comprehensive checks for all thermal-affecting specs
    - Handles both top-level and nested parameters

- ✅ `reset_thermal_cache()` function in `thermal.py`
    - Clears _cache, lazily-computed properties
    - Preserves _hours DataFrame with results

- ✅ `update_spec()` method in `BuildingEnergySimulation`
  - Intelligent routing based on thermal rerun check
    - Proper cascade of simulation updates
    - Cache invalidation for reports

- ✅ Import statements updated in `building_energy.py`

### Testing Approach

- Use `unittest` framework
- Test cases should verify:
  1. Spec comparison detects thermal changes correctly
  2. Spec comparison ignores non-thermal changes
    3. Cache reset preserves _hours DataFrame
  4. update_spec with thermal change recreates everything
  5. update_spec without thermal change preserves _hours values

## Code Locations

- Thermal functions: `/src/openbes/simulations/thermal.py` (lines ~1310-1484)
- update_spec method: `/src/openbes/simulations/building_energy.py` (lines ~1313-1413)
- Imports: `/src/openbes/simulations/building_energy.py` (line 14)

## Important Notes

- Do NOT create report.md files or write md files to console - show results in-chat or with in-memory files
- Thermal calculation is expensive (~seconds per run)
- The _hours DataFrame is the "value" - preserving it avoids recomputation
- Always reset cached outputs after spec updates
- Error handling should be conservative - fail fast on unexpected state changes

