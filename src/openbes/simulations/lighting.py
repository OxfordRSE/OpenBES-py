from importlib.resources import files

from pandas import DataFrame, read_csv, Series
import logging

from .base import EnergyUseSimulation
from .occupancy import OccupationSimulation
from ..types import OpenBESSpecification, LIGHTING_TECHNOLOGIES, LIGHTING_BALLASTS, LIGHTING_CONTROL, ENERGY_SOURCES

logger = logging.getLogger(__name__)


class LightingSimulation(EnergyUseSimulation):
    occupancy: OccupationSimulation
    _lighting_heat: float
    
    def __init__(self, spec: OpenBESSpecification, occupancy: OccupationSimulation = None):
        super().__init__(spec=spec)
        self.occupancy = occupancy or OccupationSimulation(spec=spec)

    def get_w_per_luminaire(self, zone: int) -> float:
        """kWh per day for a specific zone based on lighting system specifications.
        """
        lamp_number = getattr(self.spec, f"lighting_system_lamp_number_z{zone}")
        tech = getattr(self.spec, f"lighting_system_tech_z{zone}")
        ballast = getattr(self.spec, f"lighting_system_ballast_z{zone}")
        lamp_power = getattr(self.spec, f"lighting_system_lamp_power_z{zone}")
    
        try:
            if tech in [
                LIGHTING_TECHNOLOGIES.IC,
                LIGHTING_TECHNOLOGIES.HAL,
                LIGHTING_TECHNOLOGIES.LED
            ]:
                return float(lamp_power * lamp_number)
            if ballast == LIGHTING_BALLASTS.BE and tech == LIGHTING_TECHNOLOGIES.FT_T8:
                d = read_csv(str(files('openbes.simulations.lighting_data') / "lamp_ft_t8_be.csv"))
                return float(d.loc[(d["lamp_power"] == lamp_power)][f"lamp_number_{lamp_number}"].values[0])
            d = read_csv(str(files("openbes.simulations.lighting_data") / f"lamp_{tech.name.lower()}.csv"))
            return float(d.loc[(d["lamp_power"] == lamp_power)][f"lamp_number_{lamp_number}"].values[0])
        except (AttributeError, FileNotFoundError, KeyError, IndexError) as e:
            logger.warning(f"Badly matched self.spec for zone {zone} [{e.__class__.__name__}: {e}]")
        except Exception as e:
            logger.error(e, exc_info=True)
    
        return 0.0
    
    def get_kwh_per_day_for_zone(self, zone: int) -> float:
        """Calculate the kWh per day for a specific zone based on lighting system specifications.
        Args:
            self.spec (OpenBESSpecification): The building specifications self.spec data class.
            zone (int): The zone number to calculate kWh/day for.
        Returns:
            float: The kWh per day for the specified zone.
        """
        power_per_luminaire = self.get_w_per_luminaire(zone)
        luminary_number = getattr(self.spec, f"lighting_system_luminary_number_z{zone}")
        if luminary_number is None:
            logger.warning("Inadequate data to calculate lighting power for zone %d", zone)
            return 0.0
    
        power_per_zone = power_per_luminaire * luminary_number
    
        try:
            zone_number = getattr(self.spec, f"lighting_system_similar_zone_number_z{zone}")
            operating_hours = getattr(self.spec, f"lighting_system_operating_hours_z{zone}")
            simultaneity_factor = getattr(self.spec, f"lighting_system_simultaneity_factor_z{zone}")
    
            return power_per_zone * zone_number * simultaneity_factor * operating_hours / 1000.0
        except AttributeError:
            logger.warning("Inadequate data to calculate lighting power for zone %d", zone)
        except Exception as e:
            logger.error(e, exc_info=True)
        return 0.0
    
    def get_kwh_per_day_per_zone(self) -> DataFrame:
        """Calculate the kWh per day per zone based on lighting system specifications.
        Args:
            self.spec (OpenBESSpecification): The building specifications self.spec data class.
        Returns:
            DataFrame: A DataFrame containing kWh per day per zone.
        """
        zones = [f"Zone type {i}" for i in range(1, 7)]
        return DataFrame(
            [self.get_kwh_per_day_for_zone(i) for i in range(1, 7)],
            index=zones,
            columns=["kWh/day"]
        )
    
    def get_kwh_per_month_per_zone(self) -> DataFrame:
        """
        Calculate the kWh per month per zone based on lighting system specifications and operational hours per month.
        Args:
            self.spec (OpenBESSpecification): The building specifications self.spec data class.
        Returns:
            DataFrame: kWh used by each zone in each requested month
        """
        df = self.get_kwh_per_day_per_zone()
        operational_days_df = self.occupancy.occupied_days_per_month.copy()
        cross = df["kWh/day"].values[:, None] * operational_days_df.values
        return DataFrame(cross, columns=operational_days_df.index, index=df.index)
    
    def get_kwh_per_month(self) -> Series:
        """
        Calculate the kWh used by lighting in each month.
        Args:
            self.spec (OpenBESSpecification): The building specifications self.spec data class.
        Returns:
            DataFrame: The energy used on lighting in the building in kWh.
        """
        per_month = self.get_kwh_per_month_per_zone().sum()
        per_month.name = "kWh/month"
        return per_month

    @property
    def lights_on(self) -> 'Series[bool]':
        """Hourly lights on status.
        [Hourly Simulation column KJ]
    
        Lights are considered to be on during occupied hours between the specified on and off times.
        """
        if 'lights_on' not in self._hours.columns:
            df = self.occupancy.occupancy
            self._hours['lights_on'] = False
            on_time = self.spec.lighting_on_time
            off_time = self.spec.lighting_off_time
            if on_time is not None and off_time is not None:
                i = df.index.names.index('hour')
                self._hours['lights_on'] = df.apply(
                    lambda r: r['is_occupied'] and (on_time < r.name[i] <= off_time), axis=1
                )
        return self._hours['lights_on']

    @property
    def lighting_ratio(self) -> 'Series[float]':
        """Calculate the lighting ratio based on building specifications.
        [Hourly Simulation column KI]
        """
        if 'lighting_ratio' not in self._hours.columns:
            self._hours['lighting_ratio'] = self.lights_on * self.spec.lighting_simultaneity_factor
        return self._hours['lighting_ratio']

    @property
    def parasitic_heat(self) -> float:
        """Calculate the parasitic heat from lighting in W/m2.
        W,pc [Hourly Simulation column KR]
    
        Parasitic heat from lighting is modelled using EN 15193 Annex F which gives typical yearly values
        for school buildings.
        """
        if self.spec.parameters.lighting_on_off is not None and not self.spec.parameters.lighting_on_off:
            return 0.0
        # (emergency_kWh_per_m2_year + standby_kWh_per_m2_year) / hours_per_year * 1000 kW_per_W
        return (1 + 5) / 8760 * 1000

    @property
    def lighting_heat(self) -> float:
        """Calculate the lighting heat gains in W/m2.
        [Inputs cell C147]
    
        Heat from lighting is modelled using EN 15193 Annex F which gives typical yearly values
        for school buildings.
    
        The model accounts for differences in automatic and manual lighting controls.
        """
        if not hasattr(self, '_lighting_heat') or self._lighting_heat is None:
            if self.spec.parameters.lighting_on_off is not None and not self.spec.parameters.lighting_on_off:
                return 0.0
            FC = 1.0  # correction factor for building type (schools)
            kWh_per_year_m2 = 20.0
            tD = 1800.0  # daylight usage hours
            tN = 200.0  # night usage hours
            FD = 1.0 if self.spec.lighting_control == LIGHTING_CONTROL.Manual else 0.9  # daylight control factor
            F0 = 1.0 if self.spec.lighting_control == LIGHTING_CONTROL.Manual else 0.9  # general control factor
            self._lighting_heat = (
                    (FC * kWh_per_year_m2 / 1000 * ((tD * FD * F0) + (tN * F0))) *
                    (5 / 8760 * (8760 - (tD + tN))) *
                    1000 /
                    8760
            )
        return self._lighting_heat

    @property
    def energy_use(self) -> DataFrame:
        """Lighting energy use in kWh for each hour of the year.

        NOTE: This currently averages annual energy use by lighting over each hour of the year.
         A more sensible implementation will spread the usage over occupied hours only,
         taking into account lighting on/off times and lighting ratio.
        """
        if self._energy_use[ENERGY_SOURCES.Electricity].hasnans:
            self._energy_use[ENERGY_SOURCES.Electricity] = self.get_kwh_per_month().sum().sum() / len(self._energy_use)
        return self._energy_use
        