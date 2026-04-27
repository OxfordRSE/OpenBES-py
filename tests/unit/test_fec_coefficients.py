"""Tests for the fec_coefficients field on OpenBESSpecificationV2.

Covers:
  - Schema-level validation: all valid input shapes are accepted; invalid ones are rejected.
  - Model behaviour: .root unwrapping, defaults, partial and full custom overrides.
  - BuildingEnergySimulation.per_FEC_coefficients: correct DataFrame produced for each path
    (preset country string, preset country enum, empty custom object, partial override,
    full override, None / legacy country field).
"""

import unittest

from pydantic import ValidationError

from openbes import BuildingEnergySimulation, OpenBESSpecification
from openbes.examples import HOLYWELL_HOUSE_SPEC
from openbes.schemas import (
    CustomFECCoefficients,
    FECCoefficients,
    FECCoefficientsRow,
    OpenBESSpecificationV2,
    SUPPORTEDCOUNTRIES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# "Other" country row from per_FEC_coefficients.csv — the baseline for custom specs.
OTHER_DEFAULTS = {
    "Electricity": {"PEC/kWh FEC": 1.5, "PECnr/kWh FEC": 1.15, "kgCO2/kWh FEC": 0.1},
    "Diesel": {"PEC/kWh FEC": 1.273, "PECnr/kWh FEC": 1.268, "kgCO2/kWh FEC": 0.311},
    "LPG": {"PEC/kWh FEC": 1.168, "PECnr/kWh FEC": 1.166, "kgCO2/kWh FEC": 0.254},
    "Natural gas": {
        "PEC/kWh FEC": 1.161,
        "PECnr/kWh FEC": 1.159,
        "kgCO2/kWh FEC": 0.239,
    },
    "Biomass": {"PEC/kWh FEC": 1.037, "PECnr/kWh FEC": 0.034, "kgCO2/kWh FEC": 0.018},
    "Pellets": {"PEC/kWh FEC": 1.542, "PECnr/kWh FEC": 0.082, "kgCO2/kWh FEC": 0.044},
}

UK_ELECTRICITY = {
    "PEC/kWh FEC": 1.501,
    "PECnr/kWh FEC": 1.134756,
    "kgCO2/kWh FEC": 0.136,
}
SPAIN_ELECTRICITY = {
    "PEC/kWh FEC": 2.403,
    "PECnr/kWh FEC": 2.007,
    "kgCO2/kWh FEC": 0.357,
}

ENERGY_SOURCES = ["Electricity", "Diesel", "LPG", "Natural gas", "Biomass", "Pellets"]
CSV_COLS = ["PEC/kWh FEC", "PECnr/kWh FEC", "kgCO2/kWh FEC"]


def _sim_with_fec(fec_coefficients):
    """Return a BuildingEnergySimulation whose spec has the given fec_coefficients value."""
    from copy import deepcopy

    spec = deepcopy(HOLYWELL_HOUSE_SPEC)
    spec.fec_coefficients = fec_coefficients
    return BuildingEnergySimulation(spec=spec)


# ---------------------------------------------------------------------------
# 1. Schema / Pydantic validation
# ---------------------------------------------------------------------------


class TestFECCoefficientsSchemaValidation(unittest.TestCase):
    """fec_coefficients accepts all valid shapes and rejects invalid ones."""

    # --- valid inputs -------------------------------------------------------

    def test_accepts_preset_country_string(self):
        for country in ("Spain", "USA", "France", "UK", "Other"):
            with self.subTest(country=country):
                spec = OpenBESSpecificationV2(fec_coefficients=country)
                self.assertIsInstance(spec.fec_coefficients, FECCoefficients)
                self.assertEqual(
                    spec.fec_coefficients.root, SUPPORTEDCOUNTRIES(country)
                )

    def test_accepts_preset_country_enum(self):
        for member in SUPPORTEDCOUNTRIES:
            with self.subTest(member=member):
                spec = OpenBESSpecificationV2(fec_coefficients=member)
                self.assertIsInstance(spec.fec_coefficients.root, SUPPORTEDCOUNTRIES)
                self.assertEqual(spec.fec_coefficients.root, member)

    def test_accepts_empty_object(self):
        spec = OpenBESSpecificationV2(fec_coefficients={})
        self.assertIsInstance(spec.fec_coefficients.root, CustomFECCoefficients)

    def test_accepts_partial_object_electricity_only(self):
        spec = OpenBESSpecificationV2(
            fec_coefficients={"Electricity": {"PEC_per_kWh_FEC": 9.99}}
        )
        self.assertIsInstance(spec.fec_coefficients.root, CustomFECCoefficients)
        self.assertEqual(spec.fec_coefficients.root.Electricity.PEC_per_kWh_FEC, 9.99)

    def test_accepts_partial_object_natural_gas_alias(self):
        """'Natural gas' (with space) is the JSON alias for Natural_gas."""
        spec = OpenBESSpecificationV2(
            fec_coefficients={"Natural gas": {"PEC_per_kWh_FEC": 1.2}}
        )
        self.assertIsInstance(spec.fec_coefficients.root, CustomFECCoefficients)
        self.assertEqual(spec.fec_coefficients.root.Natural_gas.PEC_per_kWh_FEC, 1.2)

    def test_accepts_full_object_all_sources_all_columns(self):
        full = {
            src: {
                "PEC_per_kWh_FEC": 1.0,
                "PECnr_per_kWh_FEC": 0.9,
                "kgCO2_per_kWh_FEC": 0.05,
            }
            for src in (
                "Electricity",
                "Diesel",
                "LPG",
                "Natural gas",
                "Biomass",
                "Pellets",
            )
        }
        spec = OpenBESSpecificationV2(fec_coefficients=full)
        root = spec.fec_coefficients.root
        self.assertIsInstance(root, CustomFECCoefficients)
        for attr in (
            "Electricity",
            "Diesel",
            "LPG",
            "Natural_gas",
            "Biomass",
            "Pellets",
        ):
            row = getattr(root, attr)
            self.assertIsInstance(row, FECCoefficientsRow)

    def test_accepts_none(self):
        spec = OpenBESSpecificationV2(fec_coefficients=None)
        self.assertIsNone(spec.fec_coefficients)

    def test_accepts_omitted(self):
        spec = OpenBESSpecificationV2()
        self.assertIsNone(spec.fec_coefficients)

    # --- invalid inputs -----------------------------------------------------

    def test_rejects_unknown_country_string(self):
        with self.assertRaises(ValidationError):
            OpenBESSpecificationV2(fec_coefficients="Narnia")

    def test_rejects_extra_property_in_row(self):
        with self.assertRaises(ValidationError):
            OpenBESSpecificationV2(
                fec_coefficients={"Electricity": {"unknown_field": 1.0}}
            )

    def test_rejects_extra_property_in_custom_object(self):
        with self.assertRaises(ValidationError):
            OpenBESSpecificationV2(fec_coefficients={"UnknownSource": {}})

    def test_rejects_non_numeric_row_value(self):
        with self.assertRaises(ValidationError):
            OpenBESSpecificationV2(
                fec_coefficients={"Electricity": {"PEC_per_kWh_FEC": "not-a-number"}}
            )


# ---------------------------------------------------------------------------
# 2. CustomFECCoefficients default values
# ---------------------------------------------------------------------------


class TestCustomFECCoefficientsDefaults(unittest.TestCase):
    """An empty {} custom object must carry the correct 'Other' defaults."""

    def setUp(self):
        spec = OpenBESSpecificationV2(fec_coefficients={})
        self.root = spec.fec_coefficients.root

    def _check_row(self, attr, pec, pec_nr, co2):
        row = getattr(self.root, attr)
        self.assertAlmostEqual(row.PEC_per_kWh_FEC, pec, places=6)
        self.assertAlmostEqual(row.PECnr_per_kWh_FEC, pec_nr, places=6)
        self.assertAlmostEqual(row.kgCO2_per_kWh_FEC, co2, places=6)

    def test_electricity_defaults(self):
        self._check_row("Electricity", 1.5, 1.15, 0.1)

    def test_diesel_defaults(self):
        self._check_row("Diesel", 1.273, 1.268, 0.311)

    def test_lpg_defaults(self):
        self._check_row("LPG", 1.168, 1.166, 0.254)

    def test_natural_gas_defaults(self):
        self._check_row("Natural_gas", 1.161, 1.159, 0.239)

    def test_biomass_defaults(self):
        self._check_row("Biomass", 1.037, 0.034, 0.018)

    def test_pellets_defaults(self):
        self._check_row("Pellets", 1.542, 0.082, 0.044)


# ---------------------------------------------------------------------------
# 3. BuildingEnergySimulation.per_FEC_coefficients DataFrame
# ---------------------------------------------------------------------------


class TestPerFECCoefficientsDataFrame(unittest.TestCase):
    """per_FEC_coefficients returns correct DataFrames for every fec_coefficients path."""

    # helpers ----------------------------------------------------------------

    def _assert_row(self, df, source, expected):
        for col, val in expected.items():
            with self.subTest(source=source, col=col):
                self.assertAlmostEqual(df.loc[source, col], val, places=6)

    def _assert_all_other_defaults(self, df, except_source=None):
        for src in ENERGY_SOURCES:
            if src == except_source:
                continue
            self._assert_row(df, src, OTHER_DEFAULTS[src])

    # preset country ---------------------------------------------------------

    def test_preset_country_string_uk_electricity(self):
        sim = _sim_with_fec("UK")
        df = sim.per_FEC_coefficients
        self._assert_row(df, "Electricity", UK_ELECTRICITY)

    def test_preset_country_enum_uk_electricity(self):
        sim = _sim_with_fec(FECCoefficients(SUPPORTEDCOUNTRIES.UK))
        df = sim.per_FEC_coefficients
        self._assert_row(df, "Electricity", UK_ELECTRICITY)

    def test_preset_country_string_spain_electricity(self):
        sim = _sim_with_fec("Spain")
        df = sim.per_FEC_coefficients
        self._assert_row(df, "Electricity", SPAIN_ELECTRICITY)

    def test_preset_country_has_all_six_sources(self):
        sim = _sim_with_fec("UK")
        df = sim.per_FEC_coefficients
        self.assertEqual(set(df.index), set(ENERGY_SOURCES))

    def test_preset_country_has_all_three_columns(self):
        sim = _sim_with_fec("UK")
        df = sim.per_FEC_coefficients
        for col in CSV_COLS:
            self.assertIn(col, df.columns)

    # empty custom object ----------------------------------------------------

    def test_empty_custom_object_equals_other_defaults(self):
        sim = _sim_with_fec(FECCoefficients(CustomFECCoefficients()))
        df = sim.per_FEC_coefficients
        self._assert_all_other_defaults(df)

    def test_empty_custom_object_has_all_six_sources(self):
        sim = _sim_with_fec(FECCoefficients(CustomFECCoefficients()))
        df = sim.per_FEC_coefficients
        self.assertEqual(set(df.index), set(ENERGY_SOURCES))

    # partial custom override ------------------------------------------------

    def test_partial_override_electricity_pec_changes(self):
        custom = FECCoefficients(
            CustomFECCoefficients(Electricity=FECCoefficientsRow(PEC_per_kWh_FEC=9.99))
        )
        sim = _sim_with_fec(custom)
        df = sim.per_FEC_coefficients
        self.assertAlmostEqual(df.loc["Electricity", "PEC/kWh FEC"], 9.99, places=6)

    def test_partial_override_electricity_unchanged_columns_stay_as_other(self):
        custom = FECCoefficients(
            CustomFECCoefficients(Electricity=FECCoefficientsRow(PEC_per_kWh_FEC=9.99))
        )
        sim = _sim_with_fec(custom)
        df = sim.per_FEC_coefficients
        # Only PEC/kWh FEC changed; the other two stay at "Other" defaults.
        self.assertAlmostEqual(
            df.loc["Electricity", "PECnr/kWh FEC"],
            OTHER_DEFAULTS["Electricity"]["PECnr/kWh FEC"],
            places=6,
        )
        self.assertAlmostEqual(
            df.loc["Electricity", "kgCO2/kWh FEC"],
            OTHER_DEFAULTS["Electricity"]["kgCO2/kWh FEC"],
            places=6,
        )

    def test_partial_override_unmentioned_sources_stay_as_other(self):
        custom = FECCoefficients(
            CustomFECCoefficients(Electricity=FECCoefficientsRow(PEC_per_kWh_FEC=9.99))
        )
        sim = _sim_with_fec(custom)
        df = sim.per_FEC_coefficients
        self._assert_all_other_defaults(df, except_source="Electricity")

    def test_partial_override_natural_gas_via_alias(self):
        """Natural gas can be specified via dict with 'Natural gas' key."""
        spec_v2 = OpenBESSpecificationV2(
            fec_coefficients={"Natural gas": {"kgCO2_per_kWh_FEC": 0.999}}
        )
        from copy import deepcopy

        spec = deepcopy(HOLYWELL_HOUSE_SPEC)
        spec.fec_coefficients = spec_v2.fec_coefficients
        sim = BuildingEnergySimulation(spec=spec)
        df = sim.per_FEC_coefficients
        self.assertAlmostEqual(df.loc["Natural gas", "kgCO2/kWh FEC"], 0.999, places=6)
        # Other natural-gas columns unchanged
        self.assertAlmostEqual(
            df.loc["Natural gas", "PEC/kWh FEC"],
            OTHER_DEFAULTS["Natural gas"]["PEC/kWh FEC"],
            places=6,
        )

    # full custom override ---------------------------------------------------

    def test_full_custom_override_all_values_applied(self):
        # "Natural gas" must be passed via model_validate (its alias) because
        # CustomFECCoefficients uses extra="forbid" and the Python attr is Natural_gas.
        custom = FECCoefficients(
            CustomFECCoefficients.model_validate(
                {
                    "Electricity": {
                        "PEC_per_kWh_FEC": 2.5,
                        "PECnr_per_kWh_FEC": 2.0,
                        "kgCO2_per_kWh_FEC": 0.5,
                    },
                    "Diesel": {
                        "PEC_per_kWh_FEC": 1.3,
                        "PECnr_per_kWh_FEC": 1.27,
                        "kgCO2_per_kWh_FEC": 0.32,
                    },
                    "LPG": {
                        "PEC_per_kWh_FEC": 1.2,
                        "PECnr_per_kWh_FEC": 1.18,
                        "kgCO2_per_kWh_FEC": 0.26,
                    },
                    "Natural gas": {
                        "PEC_per_kWh_FEC": 1.17,
                        "PECnr_per_kWh_FEC": 1.16,
                        "kgCO2_per_kWh_FEC": 0.24,
                    },
                    "Biomass": {
                        "PEC_per_kWh_FEC": 1.04,
                        "PECnr_per_kWh_FEC": 0.035,
                        "kgCO2_per_kWh_FEC": 0.019,
                    },
                    "Pellets": {
                        "PEC_per_kWh_FEC": 1.55,
                        "PECnr_per_kWh_FEC": 0.083,
                        "kgCO2_per_kWh_FEC": 0.045,
                    },
                }
            )
        )
        sim = _sim_with_fec(custom)
        df = sim.per_FEC_coefficients

        expected = {
            "Electricity": (2.5, 2.0, 0.5),
            "Diesel": (1.3, 1.27, 0.32),
            "LPG": (1.2, 1.18, 0.26),
            "Natural gas": (1.17, 1.16, 0.24),
            "Biomass": (1.04, 0.035, 0.019),
            "Pellets": (1.55, 0.083, 0.045),
        }
        for src, (pec, pec_nr, co2) in expected.items():
            with self.subTest(source=src):
                self.assertAlmostEqual(df.loc[src, "PEC/kWh FEC"], pec, places=6)
                self.assertAlmostEqual(df.loc[src, "PECnr/kWh FEC"], pec_nr, places=6)
                self.assertAlmostEqual(df.loc[src, "kgCO2/kWh FEC"], co2, places=6)

    # None / absent ----------------------------------------------------------

    def test_none_fec_coefficients_falls_back_to_other(self):
        from copy import deepcopy

        spec = deepcopy(HOLYWELL_HOUSE_SPEC)
        spec.fec_coefficients = None
        spec.country = None
        sim = BuildingEnergySimulation(spec=spec)
        df = sim.per_FEC_coefficients
        self._assert_all_other_defaults(df)

    def test_legacy_country_field_still_works(self):
        """Specs using the old .country attribute (no fec_coefficients) still resolve correctly."""
        from copy import deepcopy

        spec = deepcopy(HOLYWELL_HOUSE_SPEC)
        spec.fec_coefficients = None
        spec.country = "Spain"
        sim = BuildingEnergySimulation(spec=spec)
        df = sim.per_FEC_coefficients
        self._assert_row(df, "Electricity", SPAIN_ELECTRICITY)


if __name__ == "__main__":
    unittest.main()
