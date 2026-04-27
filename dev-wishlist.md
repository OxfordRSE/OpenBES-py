# OpenBES-py Development Wishlist (Post-Excel)

## Interface

### Schema overhaul and legacy pruning

Remove fields that no longer have meaning, and tighten units/descriptions so the schema stands on its own without the
Excel context.

### Retire legacy TOML conversion assumptions
The JSON↔TOML conversion layer bakes in Excel-era defaults such as fixed zone names and index positions, which makes it harder to evolve the schema without accidental data loss. Decide whether the TOML conversion remains necessary; if not, deprecate it and simplify the pipeline to accept JSON only, or rework it to preserve arbitrary zone/system lists without lossy mapping. 

The most likely solution here is that we keep JSON -> TOML conversion so we can easily support ASHRAE 140 cases that are currently in TOML, but we remove the TOML -> JSON conversion and require all user specs to be in JSON format. This would allow us to remove the lossy mapping from the TOML conversion and simplify the codebase, while still supporting legacy ASHRAE 140 cases.

### Monthly/annual inputs
Some data are supplied to the tool in monthly format, and some in annual format. The Excel tool used monthly values for some and annual values for others, and we have inherited that inconsistency. 

We should decide on a consistent approach. It may be that there is logic to the Excel decisions (e.g. monthly electricity and gas consumption figures are used for validating the tool simulation against actual energy bill values). If this is the case, a combination of clear variable names and good documentation should remove the confusion.

### Specification/parameters/advanced inputs
The Excel tool had some specification/parameter fields that made Excel sense but not programming sense (e.g. specifications for the first Heating System were 'specifications', while those for the second were 'parameters' (advanced inputs)). 

It will be worthwhile to overhaul the specification/parameter distinction and keep everything that is actually a specification to the specification section, and things that are physics-based (e.g. specific heat capacity of air) in the parameters section. This would make the code more intuitive and reduce confusion about where to find and update different kinds of inputs.

We may wish to retain some kind of signal in the schema to indicate which fields are more or less advanced, or perhaps for what they are required (e.g. fields that are only required for certain simulations). This would allow us to provide better error messages and documentation about which fields are necessary for which simulations, and to guide users in filling out the specification. In many cases, the presence of a default value will do much of this signalling work. 

## Documentation

### Docstrings

The codebase has quite a lot of docstrings, but their verbosity and clarity doesn't always match the complexity of the
code or the frequency with which a function is used. In several cases we still have `???` placeholders from where the
Excel logic or naming was not properly understood.

We should have docstrings that explain what a function does, what its inputs and outputs are, and any important details
about the calculation. This is especially important for complex calculations or those that are used frequently
throughout the codebase. Where functions need to be disambiguated from one another (e.g. different kinds of demand), the
docstring should clarify the distinction.

Most developers in the future of this project will primarily be energy scientists, not software engineers, so areas of
the code that use software engineering tricks or unusual patterns should have hand-holding documentation (e.g. why we
extract the core of the thermal simulation into a JIT-compiled function).

References to Excel can be removed from docstrings and the docstrings should stand on their own without requiring
familiarity with the Excel tool. We can still mention Excel where the logic of the code takes a path that could be
simplified or improved but exists in its current form because that's how it was in Excel and we've not yet updated it.

### CI Documentation

CI should be much better documented, remembering that future developers may not be familiar with GitHub Actions or CI in
general. The CI workflow should be clearly documented in the README, and the individual steps should have comments
explaining what they do and why they are necessary.

### Magic Numbers
Several calculations invoke magic numbers that were hardcoded in Excel. These should be replaced with named constants. Most should turn up with a text-search for `hardcoded`.

### Internal function names
Some internal function names use shorthand where more explicit names would improve readability. For example, the heating/cooling simulations use names like `phi_hc_nd_actual` instead of `demand_actual`. Some thought should go into these names to disambiguate them from one another given we have multiple demands.

These occurrences are particularly prevalent in heating/cooling simulations and in the thermal/solar calculations.

### Naming scheme and consistency
There are several areas where a consistent and clear naming scheme would help readability and maintainability of the codebase. Changes would include disambiguating different kinds of demand (e.g. actual demand, demand with HVAC fully on, demand per unit area), having a consistent structure for units (e.g. always use W rather than kW unless noted in the function name), and differentiating in function names whether values are scaled (W/m²). Ideally we should be able to read at a glance whether a value is a total, per unit area, or per person, and whether it is in W or kW. This would be a significant refactor but would improve readability and reduce the chance of unit errors.

## Refactoring

### Refocus unit tests on functionality vs. Excel parity

Many unit tests compare against `hh_*.csv` fixtures that mirror Excel outputs, which locks in legacy behaviors. Replace
these with scenario-based tests that assert invariants, unit consistency, and known physical relationships (e.g., sign
and magnitude checks, conservation rules), and build new fixtures from JSON specs rather than Excel-exported CSVs.

### Relax ASHRAE case tests to standard targets

The ASHRAE 140 case tests currently compare outputs to precomputed CSV expectations, including exact peaks and totals,
tying them to Excel parity rather than the standard’s target ranges. Update these tests to focus on ASHRAE acceptance
criteria only and report deviations from target ranges without enforcing exact Excel values. Add a digest of ASHRAE 140
performance vs other tools as a test artifact to track improvements over time.

### Adopt schema-driven specifications in core simulations

Core simulations still rely on legacy dataclasses and flattened spec fields (e.g., `cooling_system1_*`) despite the
newer schema supporting arrays and nested objects. The simulation entrypoints should be refactored to consume
`OpenBESSpecificationV2` (or the schema-derived models) directly, removing the legacy dataclasses and updating internal
lookups to use the new structure.

The schema already models arrays of heating/cooling/ventilation/lighting systems, but the implementation and conversion
tooling still hard-code small fixed counts (e.g., two HVAC systems, six lighting slots). Refactor the simulations and
conversions to iterate over arbitrary-length arrays and return results aligned with those arrays in outputs.

### Improve error handling and simulation resilience

Several simulations raise hard errors on missing inputs (e.g., HVAC system attributes, geometry validation, occupancy
indexing), which stops the full simulation. Replace these with structured warnings that skip the affected subsystem,
record the issue in the log, and continue with other outputs; only error out if no modules can run at all (and possibly
not even then for non-critical simulations). This would allow users to get partial results and identify issues without
losing all outputs, and would allow users to start getting results rapidly while inputting their specification.

### Possible: Refactor reports into their respective simulations
Not sure on the value of this. 

Advantages:
- Keeps all the logic for a given simulation in one place, improving readability and maintainability.
- Allows us to keep prerequisite checks and error handling in the simulation rather than spreading it out into the report generator
- Allows us to add new simulations without needing to add to spaghetti code in the report generator
- Simplifies the report generator

Disadvantages:
- The report structure is governed by the API specification which the simulation logic should largely be agnostic about
- Having the report generator look similar to the API specification makes it easier to detect where the simulation logic is missing or incomplete, as the report will be missing expected fields. If the report generation is mixed into the simulations, it may be less obvious when a field is missing or not being calculated.
- Some reports will have to remain centralised anyway, because they aggregate results from multiple simulations.

On balance, it's probably worth refactoring. We can accept as a necessary consequence that simulation reports will have to produce an output that matches the API specification, but that can be usefully enforced with the Pydantic models generated from the OpenAPI schema.

### Support Pythonic outputs
Currently, the table outputs are all in CSV format. It would be useful to provide outputs as DataFrames etc. for dealing with downstream Python code. This should be relatively easy to do by adding utility functions to convert DataFrames to CSV (reducing code duplication in report generation), and simply not using them if Pythonic outputs are requested.

### Excel era inconsistencies in calculations

There are one or two areas where Excel has inconsistencies or mistakes. These can be corrected.

There are some more general approaches which might be relatively simple Python refactors that would improve the
consistency of the tool. For example, heating/cooling systems could quite easily be refactored to depend more precisely
on the occupation of a particular zone at a particular time. The 'common areas' and 'other' zones, for example, use the
same occupancy profile as the 'office' zone -- we could refactor to allow them to use their own occupancy profiles.

### Logging
Each simulation should provide a useful structured log of its behaviour. This can replace the current `logging`-based logging approach which is a bit spammy. Logs should include information about which subsystems were run, any warnings or errors that were raised, and any important details about the calculations (e.g. if a particular zone was skipped due to missing inputs). Perhaps they might include information on how long the simulation took, when each property was calculated, etc. 

This would allow users to understand what happened during the simulation and identify any issues without needing to debug the code directly. It would also allow us to provide better error messages and guidance for users when they encounter issues with their specifications.
