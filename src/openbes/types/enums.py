from enum import Enum

class ListableEnum(Enum):
    @classmethod
    def list_values(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def get_by_index(cls, index):
        return cls(cls.list_values()[index])

    @classmethod
    def get_by_value(cls, value):
        v = value.strip().lower()
        for member in cls:
            if member.value.strip().lower() == v:
                return member
        raise ValueError(f"{value} is not a valid value for {cls.__name__}")
    
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.value == other.value

    def __hash__(self):
        return hash(self.value)

    def __lt__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return list(type(self)).index(self) < list(type(self)).index(other)

    def __gt__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return list(type(self)).index(self) > list(type(other)).index(other)

    def __le__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return list(type(self)).index(self) <= list(type(other)).index(other)

    def __ge__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return list(type(self)).index(self) >= list(type(other)).index(other)


class MONTHS(ListableEnum):
    Jan = "Jan"
    Feb = "Feb"
    Mar = "Mar"
    Apr = "Apr"
    May = "May"
    Jun = "Jun"
    Jul = "Jul"
    Aug = "Aug"
    Sep = "Sep"
    Oct = "Oct"
    Nov = "Nov"
    Dec = "Dec"


class DAYS(ListableEnum):
    Mon = "Mon"
    Tue = "Tue"
    Wed = "Wed"
    Thu = "Thu"
    Fri = "Fri"
    Sat = "Sat"
    Sun = "Sun"


class ENERGY_SOURCES(ListableEnum):
    Electricity = "Electricity"
    Diesel = "Diesel"
    LPG = "LPG"
    Natural_gas = "Natural gas"
    Biomass = "Biomass"
    Pellets = "Pellets"


class ENERGY_USE_CATEGORIES(ListableEnum):
    Others = "Others"
    Building_standby = "Building standby"
    Lighting = "Lighting"
    Hot_water = "Hot water"
    Ventilation = "Ventilation"
    Cooling = "Cooling"
    Heating = "Heating"


class FLOORS(ListableEnum):
    Ground = "ground"
    First = "first"
    Second = "second"
    Third = "third"
    Fourth = "fourth"


class OCCUPATION_ZONES(ListableEnum):
    Office = "office"
    Teaching = "teaching"
    Canteen = "canteen"
    Common_areas = "common_areas"
    Other = "other"


def get_zone_number(zone: OCCUPATION_ZONES) -> str:
    return {
        OCCUPATION_ZONES.Office: "1",
        OCCUPATION_ZONES.Teaching: "2",
        OCCUPATION_ZONES.Canteen: "3",
        OCCUPATION_ZONES.Common_areas: "4",
        OCCUPATION_ZONES.Other: "5",
    }[zone]


class LIGHTING_TECHNOLOGIES(ListableEnum):
    FT_T8 = "Tubular fluorescent T8"
    FT_T5 = "Tubular fluorescent T5"
    FC = "Compact fluorescent"
    IC = "Incandescent"
    HAL = "Halogen"
    VM = "Mercury vapor"
    VS = "Sodium vapour"
    IM = "Metal halide"
    IND = "Induction"
    LED = "LED"


class LIGHTING_BALLASTS(ListableEnum):
    BE = "Electronic ballast"
    BF = "Ferromagnetic ballast"


class LIGHTING_CONTROL(ListableEnum):
    Manual = "Manual"
    Automatic = "Automatic"


class ORIENTATIONS(ListableEnum):
    """
    Cardinal directions for building orientation. These are relative to the building layout, with the assumption that
    "Up" corresponds to the front of the building.
    """
    Up = "Up"
    Right = "Right"
    Down = "Down"
    Left = "Left"


class COMPASS_POINTS(ListableEnum):
    North = "North"
    NorthEast = "NorthEast"
    East = "East"
    SouthEast = "SouthEast"
    South = "South"
    SouthWest = "SouthWest"
    West = "West"
    NorthWest = "NorthWest"


class THERMAL_BREAKS(ListableEnum):
    Facade_ground = "Façade (ground)"
    Facade_intermediate = "Façade (intermediate)"
    Facade_roof = "Façade (roof)"
    Windows = "Windows (lintels, jambs, sills)"
    Shading = "Shading devices (roller blinds)"


class HEAT_CAPACITY_CLASSES(ListableEnum):
    Very_light = "Very light"
    Light = "Light"
    Medium = "Medium"
    Heavy = "Heavy"
    Very_heavy = "Very heavy"
    Custom_value = "Custom Value"


class TERRAINS(ListableEnum):
    Open = "Open terrain"
    Country = "Country"
    Urban = "Urban"


class HEATING_SYSTEM_TYPES(ListableEnum):
    Electric_heating_radiators = "Electric heating (radiators)"
    Electric_boiler = "Electric boiler"
    Conventional_boiler = "Conventional boiler"
    Low_temperature_boiler = "Low temperature boiler"
    Condensing_boiler = "Condensing boiler"
    Biomass_boiler = "Biomass boiler"
    Heat_pump = "Heat pump"


class COOLING_SYSTEM_TYPES(ListableEnum):
    Heat_pump = "Heat pump"
