# OpenBES-py Development Wishlist (Post-Excel)

## Index
- [Schema overhaul and legacy pruning](#schema-overhaul-and-legacy-pruning)
- [Remove correction-factor parameters](#remove-correction-factor-parameters)
- [Adopt schema-driven specifications in core simulations](#adopt-schema-driven-specifications-in-core-simulations)
- [Generalize HVAC/lighting system handling](#generalize-hvaclighting-system-handling)
- [Retire legacy TOML conversion assumptions](#retire-legacy-toml-conversion-assumptions)
- [Restructure validation data inputs/outputs](#restructure-validation-data-inputsoutputs)
- [Refocus unit tests on functionality vs. Excel parity](#refocus-unit-tests-on-functionality-vs-excel-parity)
- [Relax ASHRAE case tests to standard targets](#relax-ashrae-case-tests-to-standard-targets)
- [Improve error handling and simulation resilience](#improve-error-handling-and-simulation-resilience)
- [Streamline Excel-era calculations and placeholders](#streamline-excel-era-calculations-and-placeholders)

## Schema overhaul and legacy pruning
:warning: **External API change.** The current JSON Schema still encodes placeholder enums, [UNUSED] fields, and Excel-era assumptions (e.g., parameters flagged as unused, enumerations with placeholder wording). A focused pass should remove or rename fields that no longer have meaning, tighten units/descriptions, and turn placeholder enums into explicit, documented options so the schema stands on its own without the Excel context. **Estimate:** 3–5 days.【./src/openbes/schemas/OpenBES.schema.json†L17-L1100】

## Remove correction-factor parameters
:warning: **External API change.** Correction-factor parameters are spread across the schema, generated models, conversion layers, example data, and live simulations, yet they appear to exist solely for Excel parity. The next step is to delete these parameters end-to-end and replace any remaining usage with direct physics-based inputs or explicit user overrides where needed. **Estimate:** 2–4 days.【./src/openbes/schemas/OpenBES.schema.json†L815-L929】【./src/openbes/simulations/geometry.py†L604-L823】【./src/openbes/simulations/climate.py†L221-L1075】

## Adopt schema-driven specifications in core simulations
:warning: **External API change.** Core simulations still rely on legacy dataclasses and flattened spec fields (e.g., `cooling_system1_*`) despite the newer schema supporting arrays and nested objects. The simulation entrypoints should be refactored to consume `OpenBESSpecificationV2` (or the schema-derived models) directly, removing the legacy dataclasses and updating internal lookups to use the new structure. **Estimate:** 5–10 days.【./src/openbes/types/dataclasses.py†L1-L220】【./src/openbes/simulations/cooling.py†L24-L90】

## Generalize HVAC/lighting system handling
:warning: **External API change.** The schema already models arrays of heating/cooling/ventilation/lighting systems, but the implementation and conversion tooling still hard-code small fixed counts (e.g., two HVAC systems, six lighting slots). Refactor the simulations and conversions to iterate over arbitrary-length arrays and return results aligned with those arrays in outputs. **Estimate:** 4–7 days.【./src/openbes/schemas/OpenBES.schema.json†L969-L1060】【./src/openbes/schemas/conversion/json_to_toml.py†L72-L235】

## Retire legacy TOML conversion assumptions
The JSON↔TOML conversion layer bakes in Excel-era defaults such as fixed zone names and index positions, which makes it harder to evolve the schema without accidental data loss. Decide whether the TOML conversion remains necessary; if not, deprecate it and simplify the pipeline to accept JSON only, or rework it to preserve arbitrary zone/system lists without lossy mapping. **Estimate:** 2–4 days.【./src/openbes/schemas/conversion/json_to_toml.py†L72-L235】

## Restructure validation data inputs/outputs
The validation outputs currently serialize monthly comparisons into CSV strings and depend on separate consumption fields in the spec, which are marked as unused. Replace this with structured validation inputs (e.g., arrays of monthly values with metadata) and structured outputs (arrays of comparison records), and ensure the model validation layer cleanly handles missing months without dropping the entire comparison. **Estimate:** 2–4 days.【./src/openbes/schemas/OpenBES.schema.json†L1009-L1431】【./src/openbes/simulations/building_energy.py†L620-L699】

## Refocus unit tests on functionality vs. Excel parity
Many unit tests compare against `hh_*.csv` fixtures that mirror Excel outputs, which locks in legacy behaviors. Replace these with scenario-based tests that assert invariants, unit consistency, and known physical relationships (e.g., sign and magnitude checks, conservation rules), and build new fixtures from JSON specs rather than Excel-exported CSVs. **Estimate:** 4–8 days.【./tests/unit/test_climate.py†L45-L241】【./tests/unit/test_heating.py†L1-L50】

## Relax ASHRAE case tests to standard targets
The ASHRAE 140 case tests currently compare outputs to precomputed CSV expectations, including exact peaks and totals, tying them to Excel parity rather than the standard’s target ranges. Update these tests to focus on ASHRAE acceptance criteria only and report deviations from target ranges without enforcing exact Excel values. **Estimate:** 2–4 days.【./tests/test_cases/test_cases.py†L1-L210】

## Improve error handling and simulation resilience
Several simulations raise hard errors on missing inputs (e.g., HVAC system attributes, geometry validation, occupancy indexing), which stops the full simulation. Replace these with structured warnings that skip the affected subsystem, record the issue in the log, and continue with other outputs; only error out if no modules can run at all. **Estimate:** 3–6 days.【./src/openbes/simulations/cooling.py†L24-L60】【./src/openbes/simulations/geometry.py†L128-L213】【./src/openbes/simulations/occupancy.py†L90-L220】

## Streamline Excel-era calculations and placeholders
There are explicit Excel-style behaviors (e.g., bootstrapping running means) and placeholder/unused parameters that can now be simplified or replaced with clearer algorithms and configuration flags. Identify which of these legacy calculations are still required and remove or normalize them to reduce code paths and improve maintainability. **Estimate:** 2–5 days.【./src/openbes/simulations/building_energy.py†L706-L740】【./src/openbes/schemas/OpenBES.schema.json†L770-L933】
