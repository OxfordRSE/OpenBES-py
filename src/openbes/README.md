# OpenBES

This is the source code for OpenBES.

This README is a place to keep development notes and tips.

## Excel sheet useful bookmarks

- Target output values: 4_XL-BES_tool!R243:R248
- Monthly energy use by energy source and use category: 5_BES_auxiliary!B128:AE142
- Above, but original calculations: 4_BES-Hourly_simulation Top of file, many columns
  - Lighting: CI4
  - Hot water: CS4
  - Ventilation: DC4
    - MV Operating period: IP118
  - Heating and Cooling:
    - Cooling monthly breakdown: AX32
      - Numbers come from AY9, in turn from HI56, in turn from summing HI118...
      - 4_BES-Inputs!C344 gives cooling system characteristics
      - 
    - Heating monthly breakdown: AN32

## Simulation implementations

- Where there are differences between the Excel implementation and OpenBES, these will be documented in **bold**.
- System specifications entered by the user are in `code font`.

### Occupancy

Occupancy is defined by an occupancy schedule, which specifies the occupied hours for each day of the week.
It accounts for public holidays.

The first day of the year is assumed to be a Monday.

### Lighting

Lighting energy use is calculated by defining lighting zones that give a number and type of lighting fixtures.
These are assumed to be operational during all occupied hours, and are scaled by a 'simultaneity factor' to 
account for the fact that not all lights will be on at the same time.

Lighting energy use is calculated as the energy used by each zone per hour, summed over all zones and hours.

### Hot water

Hot water energy use is calculated by defining a `water_system_energy_source` and a `water_system_efficiency_cop`.

The daily hot water demand is calculated by:
    demand = 4.18 * `water_demand` * (`water_reference_temperature` - `water_supply_temperature`) * (1/3600)

The energy required to meet this demand is then calculated by dividing the demand by the system efficiency:
    demand / `water_system_efficiency_cop`

This energy is then summed over all days in the year to give the annual hot water energy use.

### Ventilation

Ventilation energy use is calculated by multiplying the `ventilation_system1_rated_input_power`
by the total number of mechanical ventilation hours in the year.

Mechanical ventilation hours are calculated based on the occupancy schedule.
The basic formula is:
    mechanical_ventilation_hours = ventilation_% * day_type

Day type is 1 for occupied, 0 for unoccupied (holiday or weekend). 

Ventilation_% is defined as 1 (100%) or 0 (0%) based on whether mechanical ventilation is on or off during occupied hours.
This is in turn determined by the inputs `ventilation_system1_on_time` and `ventilation_system1_off_time`.
The off hour is considered inclusive (i.e. ventilation is turned off at the _end_ of the hour).

In short, ventilation is modelled as on for a set number of hours/day during occupied days, and off otherwise.
When on, it consumes its rated input power.

So the monthly ventilation energy use is:
    monthly_ventilation_energy_use = `ventilation_system1_rated_input_power` * occupied_days_in_month * ventilation_hours_per_day

### Cooling and heating

Cooling and heating energy use are the most complex parts of the simulation.
They both work by estimating the difference between the building's natural temperature and the desired setpoint temperature,
and then calculating the energy required to bridge that gap based on the building's thermal properties and system efficiencies.

    energy_use = efficiency * demand

#### Cooling system efficiency
The efficiency of the cooling system is calculated based on:
- nominal cooling capacity (min 0.01)
- nominal sensible cooling capacity (about 80% of nominal cooling capacity; min 0.01)
- energy efficiency ratio (cooling output:input power) (min 0.01)

    nominal_cooling_capacity = `cooling_system1_number` * `cooling_system1_nominal_capacity`
    sensible_cooling_capacity = `cooling_system1_number` * `cooling_system1_sensible_nominal_capacity`
    energy_efficiency_ratio = `cooling_system1_energy_efficifiency_ratio`
    nominal_cooling_consumption = `cooling_system1_nominal_capacity` / `cooling_system1_eer`

#### Cooling system kWh calculation
The cooling energy consumption is calculated on an hourly basis, then summed to monthly totals.
The consumption calculated below only matters when the building is occupied and the natural temperature exceeds the cooling setpoint temperature (minus tolerance).

    consumption = nominal_cooling_consumption * reference_consumption_by_temp * reference_consumption_FCP

    reference_consumption_by_temp = 
      0.1117801 + 
      0.028493334 * relative_humidity -
      0.000411156 * relative_humidity^2 +
      0.021414276 * dry_bulb_temperature +
      0.000161125 * dry_bulb_temperature^2 -
      0.000679104 * dry_bulb_temperature * relative_humidity

    reference_consumption_FCP = 
      0.2012307 - 
      0.0312175 * fan_cooling_power +
      1.9504979 * (fan_cooling_power^2) -
      1.1205104 * (fan_cooling_power^3)

    relative_humidity = 55 % (assumed constant)

    dry_bulb_temperature is taken from an hourly meteorological file for the given location

    fan_cooling_power = demand / reference_sensible_cooling_capacity

    demand = -(heat_transfer_rate * total_heating_area)/1000

    heat_transfer_rate = 
      min(cooling_target_temperature, 0) * `params.cooling_load_factor`
      [if natural_temperature > cooling_setpoint_temperature, else 0]
    
    total_heating_area = 
      (heated_zone_1_area * heated_zone_1_simultaneity_factor) + 
      (heated_zone_2_area * heated_zone_2_simultaneity_factor) +
      ...

    heated_zone_N_area = 
      `ground_floor_area_zN` + 
      `first_floor_area_zN` + 
      ...

    heated_zone_N_simultaneity_factor = 
      `cooling_system1_simultaneity_factor_[X]` [where X is the zone description e.g. office]

    reference_sensible_cooling_capacity = 
      sensible_cooling_capacity * reference_capacity_by_temp

    reference_capacity_by_temp = 
      0.500601825 -
      0.046438331 * baseline_indoor_temperature -
      0.000324724 * (baseline_indoor_temperature^2) +
      0.069957819 * target_temperature -
      0.0000342756 * (target_temperature^2) -
      0.013202081 * dry_bulb_temperature + 
      0.0000793065 * (dry_bulb_temperature^2)

    baseline_indoor_temperature is simply defined as 18.5

    target_temperature = `setpoint_summer_day` - temperature_tolerance

#### Natural temperature calculation
The natural temperature is calculated using a simplified thermal model that considers:
- External temperature (monthly averages)
- 

## Data representation

### Long format

As a stylistic choice, data are presented in "long" format, where the number of columns is known a priori, 
and the number of rows can (theoretically) vary.

This means, for example, that a data frame of monthly energy consumption by lighting zone will have columns
representing the months (because the number of months is known), and rows representing the lighting zones 
(because the number of zones can vary).

### Operational days/month

Operational days/month count is used for scaling daily energy use to monthly energy use. 
In the case of lighting, for July and August, this value is hardcoded, whereas for other months and other
energy uses it is calculated based on the hourly simulation and occupancy information.

### Magic numbers

The heating/cooling calculation uses a number of "magic numbers" (i.e., hardcoded constants) that are derived from regression analysis.
Perhaps eventually we can give each a sensible name, but for now they are left as-is for clarity and traceability to the original Excel implementation.

## Tool issues:

### Easy fixes

- The headings in the Ventilation usage table (4_BES-Hourly_simulation!DC8:DF8 aren't quite right. I think the Operation one is hours rather than days, and the total should be ventilation rather than water.
- 