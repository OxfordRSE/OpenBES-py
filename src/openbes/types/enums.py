from enum import Enum

class ListableEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def get_by_index(cls, index):
        return cls(cls.list()[index])


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


OPERATIONAL_DAYS_PER_MONTH = {
    MONTHS.Jan: 18,
    MONTHS.Feb:	20,
    MONTHS.Mar:	23,
    MONTHS.Apr:	22,
    MONTHS.May:	23,
    MONTHS.Jun:	22,
    MONTHS.Jul:	23,
    MONTHS.Aug:	23,
    MONTHS.Sep:	22,
    MONTHS.Oct:	23,
    MONTHS.Nov:	22,
    MONTHS.Dec:	17,
}


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
