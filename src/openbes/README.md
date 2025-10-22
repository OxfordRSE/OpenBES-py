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
    - 

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


## Tool issues:

### Easy fixes

- The headings in the Ventilation usage table (4_BES-Hourly_simulation!DC8:DF8 aren't quite right. I think the Operation one is hours rather than days, and the total should be ventilation rather than water.
- 