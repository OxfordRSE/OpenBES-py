from pandas import DataFrame, read_csv
from os import path
import logging

from src.openbes.simulations.utils import OPERATIONAL_DAYS_DF
from src.openbes.types import OpenBESSpecification, LIGHTING_TECHNOLOGIES, LIGHTING_BALLASTS

logger = logging.getLogger(__name__)


def get_w_per_luminaire(spec: OpenBESSpecification, zone: int) -> float:
    """Calculate the kWh per day for a specific zone based on lighting system specifications.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
        zone (int): The zone number to calculate kWh/day for.
    Returns:
        float: The kWh per day for the specified zone.
    """
    lamp_number = getattr(spec, f"lighting_system_lamp_number_z{zone}")
    tech = getattr(spec, f"lighting_system_tech_z{zone}")
    ballast = getattr(spec, f"lighting_system_ballast_z{zone}")
    lamp_power = getattr(spec, f"lighting_system_lamp_power_z{zone}")

    try:
        if tech in [
            LIGHTING_TECHNOLOGIES.IC,
            LIGHTING_TECHNOLOGIES.HAL,
            LIGHTING_TECHNOLOGIES.LED
        ]:
            return float(lamp_power * lamp_number)
        if ballast == LIGHTING_BALLASTS.BE and tech == LIGHTING_TECHNOLOGIES.FT_T8:
            d = read_csv(path.join(
                path.dirname(__file__),
                "lighting_data",
                "lamp_ft_t8_be.csv"
            ))
            return float(d.loc[(d["lamp_power"] == lamp_power)][f"lamp_number_{lamp_number}"].values[0])
        d = read_csv(path.join(
            path.dirname(__file__),
            "lighting_data",
            f"lamp_{tech.name.lower()}.csv"
        ))
        return float(d.loc[(d["lamp_power"] == lamp_power)][f"lamp_number_{lamp_number}"].values[0])
    except (AttributeError, FileNotFoundError, KeyError, IndexError) as e:
        logger.warning(f"Badly matched spec for zone {zone} [{e.__class__.__name__}: {e}]")
    except Exception as e:
        logger.error(e, exc_info=True)

    return 0.0

def get_kwh_per_day_for_zone(spec: OpenBESSpecification, zone: int) -> float:
    """Calculate the kWh per day for a specific zone based on lighting system specifications.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
        zone (int): The zone number to calculate kWh/day for.
    Returns:
        float: The kWh per day for the specified zone.
    """
    power_per_luminaire = get_w_per_luminaire(spec, zone)
    luminary_number = getattr(spec, f"lighting_system_luminary_number_z{zone}")
    if luminary_number is None:
        logger.warning("Inadequate data to calculate lighting power for zone %d", zone)
        return 0.0

    power_per_zone = power_per_luminaire * luminary_number

    try:
        zone_number = getattr(spec, f"lighting_system_similar_zone_number_z{zone}")
        operating_hours = getattr(spec, f"lighting_system_operating_hours_z{zone}")
        simultaneity_factor = getattr(spec, f"lighting_system_simultaneity_factor_z{zone}")

        return power_per_zone * zone_number * simultaneity_factor * operating_hours / 1000.0
    except AttributeError:
        logger.warning("Inadequate data to calculate lighting power for zone %d", zone)
    except Exception as e:
        logger.error(e, exc_info=True)
    return 0.0

def get_kwh_per_day_per_zone(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the kWh per day per zone based on lighting system specifications.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: A DataFrame containing kWh per day per zone.
    """
    zones = [f"Zone type {i}" for i in range(1, 7)]
    return DataFrame(
        [get_kwh_per_day_for_zone(spec, i) for i in range(1, 7)],
        index=zones,
        columns=["kWh/day"]
    )

def get_kwh_per_month_per_zone(spec: OpenBESSpecification) -> DataFrame:
    """
    Calculate the kWh per month per zone based on lighting system specifications and operational hours per month.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: kWh used by each zone in each requested month
    """
    df = get_kwh_per_day_per_zone(spec)
    operational_days_df = OPERATIONAL_DAYS_DF.copy()
    operational_days_df["Jul"] = 21  # hardcoded in the Excel spreadsheet
    operational_days_df["Aug"] = 22  # hardcoded in the Excel spreadsheet
    cross = df["kWh/day"].values[:, None] * operational_days_df.values
    return DataFrame(cross, columns=operational_days_df.columns, index=df.index)

def get_kwh_per_month(spec: OpenBESSpecification) -> DataFrame:
    """
    Calculate the kWh used by lighting in each month.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: The energy used on lighting in the building in kWh.
    """
    per_month = get_kwh_per_month_per_zone(spec).sum().to_frame().transpose()
    per_month.index = ["kWh/month"]
    return per_month


