
"""
Pediatric Recruitment Engine v0.7

Targeted refinement:
- time-dependent derecruitment
- dead-space and CO2-clearance surrogates
- balance-index penalty sensitivity

Educational/research use only. Not clinical decision-support software.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List
import numpy as np


@dataclass(frozen=True)
class Patient:
    age_years: float
    weight_kg: float
    label: str = "patient"
    severity: str = "moderate"


@dataclass(frozen=True)
class VentilatorSettings:
    peep_cmH2O: float
    tidal_volume_ml_per_kg: float = 6.0
    fio2: float = 0.60


@dataclass(frozen=True)
class DiseasePreset:
    name: str
    mean_opening_pressure: float
    sd_opening_pressure: float
    mean_hysteresis_gap: float
    sd_hysteresis_gap: float
    overdistension_shift: float
    base_shunt: float
    base_dead_space: float
    heterogeneity: float
    derecruitment_rate: float  # fraction per protocol step when below closing pressure


PRESETS: Dict[str, DiseasePreset] = {
    "healthy": DiseasePreset("healthy", 4.0, 1.3, 2.2, 0.8, 15.5, 0.03, 0.20, 0.75, 0.18),
    "mild": DiseasePreset("mild", 7.0, 2.0, 3.0, 1.0, 13.5, 0.08, 0.24, 1.00, 0.24),
    "moderate": DiseasePreset("moderate", 10.0, 3.0, 4.0, 1.3, 11.5, 0.16, 0.30, 1.15, 0.30),
    "severe": DiseasePreset("severe", 14.0, 4.2, 5.0, 1.6, 9.5, 0.28, 0.38, 1.35, 0.38),
}

REGION_GRID_SHAPE = (4, 4)


def _sigmoid(x: np.ndarray, slope: float = 1.0) -> np.ndarray:
    z = np.clip(x / slope, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


def predicted_anesthetized_frc_ml(age_years: float, weight_kg: float) -> float:
    age_years = max(age_years, 0.01)
    frc_ml_per_kg = 17.0 + 13.0 * (1.0 - np.exp(-age_years / 6.0))
    return float(frc_ml_per_kg * weight_kg)


def age_modifier_for_airway_closure(age_years: float) -> float:
    return float(1.0 + 0.20 * np.exp(-age_years / 2.0))


def region_modifiers() -> List[Dict[str, float]]:
    mods = []
    rows, cols = REGION_GRID_SHAPE
    for r in range(rows):
        for c in range(cols):
            dependent = r / (rows - 1)
            lateral = abs(c - (cols - 1) / 2) / ((cols - 1) / 2)
            mods.append({
                "region_id": r * cols + c,
                "row": r,
                "col": c,
                "dependent_index": dependent,
                "opening_shift": 0.5 + 5.0 * dependent + 0.5 * lateral,
                "closing_shift": 0.2 + 2.0 * dependent,
                "overdistension_shift": 1.5 - 2.0 * dependent + 0.3 * lateral,
                "perfusion_region_weight": max(0.7 + 1.1 * dependent - 0.15 * lateral, 0.1),
                "ventilation_region_weight": max(1.2 - 0.55 * dependent, 0.1),
            })
    return mods


def generate_regional_lung_units(patient: Patient, units_per_region: int = 160, seed: int = 101) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    preset = PRESETS[patient.severity]
    age_factor = age_modifier_for_airway_closure(patient.age_years)
    mods = region_modifiers()

    arrays = {k: [] for k in [
        "region_id", "row", "col", "opening", "closing", "compliance",
        "perfusion", "ventilation_weight", "overdistension_threshold"
    ]}

    for mod in mods:
        n = units_per_region

        opening = rng.normal(
            preset.mean_opening_pressure * age_factor + mod["opening_shift"],
            preset.sd_opening_pressure * preset.heterogeneity,
            n,
        )
        opening = np.clip(opening, 0.5, 42.0)

        gap = rng.normal(preset.mean_hysteresis_gap + mod["closing_shift"], preset.sd_hysteresis_gap, n)
        gap = np.clip(gap, 0.8, 15.0)
        closing = np.clip(opening - gap, 0.0, opening - 0.1)

        compliance = rng.lognormal(mean=0.0, sigma=0.26 * preset.heterogeneity, size=n)

        perfusion = rng.lognormal(mean=0.0, sigma=0.35 * preset.heterogeneity, size=n)
        perfusion = perfusion * mod["perfusion_region_weight"]

        ventilation_weight = rng.lognormal(mean=0.0, sigma=0.20, size=n)
        ventilation_weight = ventilation_weight * mod["ventilation_region_weight"]

        overdistension_threshold = opening + preset.overdistension_shift + mod["overdistension_shift"] + rng.normal(0.0, 2.0, n)
        overdistension_threshold = np.clip(overdistension_threshold, opening + 2.5, 44.0)

        arrays["region_id"].extend([mod["region_id"]] * n)
        arrays["row"].extend([mod["row"]] * n)
        arrays["col"].extend([mod["col"]] * n)
        arrays["opening"].extend(opening)
        arrays["closing"].extend(closing)
        arrays["compliance"].extend(compliance)
        arrays["perfusion"].extend(perfusion)
        arrays["ventilation_weight"].extend(ventilation_weight)
        arrays["overdistension_threshold"].extend(overdistension_threshold)

    out = {k: np.asarray(v) for k, v in arrays.items()}
    out["perfusion"] = out["perfusion"] / out["perfusion"].sum()
    out["ventilation_weight"] = out["ventilation_weight"] / out["ventilation_weight"].sum()
    return out


def initialize_open_probability(units: Dict[str, np.ndarray], initial_peep: float = 0.0) -> np.ndarray:
    return _sigmoid(initial_peep - units["opening"], slope=0.5)


def update_open_probability(
    units: Dict[str, np.ndarray],
    previous_open_probability: np.ndarray,
    peep: float,
    preset: DiseasePreset,
    step_duration: float = 1.0,
) -> np.ndarray:
    """
    Time-dependent recruitment / derecruitment rule.

    If PEEP reaches opening pressure, opening probability increases rapidly.
    If PEEP falls below closing pressure, closure is gradual rather than instantaneous.
    This is an educational surrogate for time-dependent derecruitment after PEEP reduction.
    """
    prev = previous_open_probability

    opening_drive = _sigmoid(peep - units["opening"], slope=0.55)
    closing_drive = _sigmoid(units["closing"] - peep, slope=0.65)

    # Recruitment is fast when opening pressure is exceeded.
    recruited = np.maximum(prev, opening_drive)

    # Derecruitment is time-dependent when PEEP is below closing pressure.
    # Closure fraction grows with closing drive and disease-dependent derecruitment rate.
    closure_fraction = np.clip(preset.derecruitment_rate * closing_drive * step_duration, 0.0, 0.95)
    updated = recruited * (1.0 - closure_fraction)

    # If opening drive is strong, ensure it dominates closure.
    updated = np.maximum(updated, opening_drive)

    return np.clip(updated, 0.0, 1.0)


def regional_maps(units, open_probability, over_prob, compliance_contribution):
    rows, cols = REGION_GRID_SHAPE
    collapse = np.zeros(REGION_GRID_SHAPE)
    recruitment = np.zeros(REGION_GRID_SHAPE)
    overdistension = np.zeros(REGION_GRID_SHAPE)
    compliance = np.zeros(REGION_GRID_SHAPE)
    ventilation = np.zeros(REGION_GRID_SHAPE)

    for region in range(rows * cols):
        mask = units["region_id"] == region
        if not np.any(mask):
            continue
        r = int(units["row"][mask][0])
        c = int(units["col"][mask][0])
        recruitment[r, c] = float(np.mean(open_probability[mask]))
        collapse[r, c] = float(1.0 - recruitment[r, c])
        overdistension[r, c] = float(np.mean(over_prob[mask]))
        compliance[r, c] = float(np.sum(compliance_contribution[mask]))
        ventilation[r, c] = float(np.sum(units["ventilation_weight"][mask] * open_probability[mask]))

    if ventilation.sum() > 0:
        ventilation = ventilation / ventilation.sum()
    if compliance.sum() > 0:
        compliance = compliance / compliance.sum()

    return {
        "collapse_map": collapse,
        "recruitment_map": recruitment,
        "overdistension_map": overdistension,
        "regional_compliance_map": compliance,
        "ventilation_distribution_map": ventilation,
    }


def simulate_from_probability_state(
    patient: Patient,
    settings: VentilatorSettings,
    units: Dict[str, np.ndarray],
    open_probability: np.ndarray,
    limb: str,
    step_index: int,
    overdistension_penalty: float = 1.65,
) -> Dict[str, object]:
    peep = float(settings.peep_cmH2O)
    vt_ml = float(settings.tidal_volume_ml_per_kg * patient.weight_kg)
    preset = PRESETS[patient.severity]

    over_prob = _sigmoid(peep - units["overdistension_threshold"], slope=0.8) * open_probability

    recruited_fraction = float(np.mean(open_probability))
    collapsed_fraction = float(1.0 - recruited_fraction)
    overdistended_fraction = float(np.mean(over_prob))

    compliance_contribution = units["compliance"] * open_probability * (1.0 - 0.82 * over_prob)
    compliance_surrogate = float(np.maximum(compliance_contribution.sum() / len(compliance_contribution), 1e-6))

    driving_pressure = float(vt_ml / (compliance_surrogate * 38.0))
    plateau_pressure = float(peep + driving_pressure)

    closed_perfusion = float(np.sum(units["perfusion"] * (1.0 - open_probability)))
    shunt = float(np.clip(preset.base_shunt + 0.78 * closed_perfusion, 0.01, 0.95))

    # v0.7: dead-space burden rises with overdistension and with non-dependent ventilation dominance.
    # The last term is computed after ventilation map but requires a provisional estimate.
    dead_space_raw = preset.base_dead_space + 0.62 * overdistended_fraction
    dead_space_surrogate = float(np.clip(dead_space_raw, 0.05, 0.95))

    # CO2 clearance surrogate:
    # Improved by compliance/recruitment, worsened by dead-space burden and high pressure burden.
    pressure_burden = max(plateau_pressure - 20.0, 0.0) / 30.0
    co2_clearance_surrogate = float(np.clip(
        compliance_surrogate * (1.0 - dead_space_surrogate) / (1.0 + 0.35 * pressure_burden),
        0.0,
        2.0
    ))

    # CO2 retention risk surrogate is inverse of CO2 clearance plus dead-space burden.
    co2_retention_risk = float(np.clip((1.0 - co2_clearance_surrogate) + 0.55 * dead_space_surrogate, 0.0, 2.0))

    oxygenation_surrogate = float(settings.fio2 * (1.0 - shunt) * 100.0)
    spo2_surrogate = float(np.clip(60.0 + 40.0 * (1.0 - np.exp(-oxygenation_surrogate / 35.0)), 50.0, 100.0))

    maps = regional_maps(units, open_probability, over_prob, compliance_contribution)
    collapse_load = float(np.mean(maps["collapse_map"]))
    overdistension_load = float(np.mean(maps["overdistension_map"]))
    regional_balance = float(1.0 - collapse_load - overdistension_penalty * overdistension_load)

    vent_map = maps["ventilation_distribution_map"]
    dependent_ventilation_fraction = float(np.sum(vent_map[2:, :]))
    nondependent_ventilation_fraction = float(np.sum(vent_map[:2, :]))

    # Recalculate dead space with a small ventilation maldistribution term.
    maldistribution_penalty = max(0.0, nondependent_ventilation_fraction - dependent_ventilation_fraction) * 0.10
    dead_space_surrogate = float(np.clip(dead_space_surrogate + maldistribution_penalty, 0.05, 0.95))
    co2_clearance_surrogate = float(np.clip(
        compliance_surrogate * (1.0 - dead_space_surrogate) / (1.0 + 0.35 * pressure_burden),
        0.0,
        2.0
    ))
    co2_retention_risk = float(np.clip((1.0 - co2_clearance_surrogate) + 0.55 * dead_space_surrogate, 0.0, 2.0))

    pressure_penalty = 0.010 * min(max(plateau_pressure - 20.0, 0.0), 30.0)
    global_balance = float(recruited_fraction - overdistension_penalty * overdistended_fraction - pressure_penalty)
    gas_exchange_balance = float((oxygenation_surrogate / 100.0) * co2_clearance_surrogate)

    return {
        "label": patient.label,
        "age_years": float(patient.age_years),
        "weight_kg": float(patient.weight_kg),
        "severity": patient.severity,
        "limb": limb,
        "step_index": int(step_index),
        "PEEP": peep,
        "FiO2": float(settings.fio2),
        "VT_ml_kg": float(settings.tidal_volume_ml_per_kg),
        "FRC_ml": predicted_anesthetized_frc_ml(patient.age_years, patient.weight_kg),
        "overdistension_penalty": float(overdistension_penalty),
        "recruited_fraction": recruited_fraction,
        "collapsed_fraction": collapsed_fraction,
        "overdistended_fraction": overdistended_fraction,
        "compliance_surrogate": compliance_surrogate,
        "driving_pressure_surrogate": driving_pressure,
        "plateau_pressure_surrogate": plateau_pressure,
        "shunt_surrogate": shunt,
        "dead_space_surrogate": dead_space_surrogate,
        "co2_clearance_surrogate": co2_clearance_surrogate,
        "co2_retention_risk": co2_retention_risk,
        "oxygenation_surrogate": oxygenation_surrogate,
        "spo2_surrogate": spo2_surrogate,
        "global_balance_index": global_balance,
        "regional_balance_index": regional_balance,
        "gas_exchange_balance": gas_exchange_balance,
        "dependent_ventilation_fraction": dependent_ventilation_fraction,
        "nondependent_ventilation_fraction": nondependent_ventilation_fraction,
        **maps,
    }


def simulate_protocol(
    patient: Patient,
    ascending_peeps: Iterable[float] = range(0, 25, 2),
    descending_peeps: Iterable[float] = range(24, 1, -2),
    fio2: float = 0.60,
    vt_ml_kg: float = 6.0,
    units_per_region: int = 160,
    seed: int = 101,
    step_duration: float = 1.0,
    overdistension_penalty: float = 1.65,
) -> List[Dict[str, object]]:
    units = generate_regional_lung_units(patient, units_per_region=units_per_region, seed=seed)
    preset = PRESETS[patient.severity]
    open_prob = initialize_open_probability(units, initial_peep=0.0)

    rows = []
    step = 0
    for limb, peeps in [("ascending", ascending_peeps), ("descending", descending_peeps)]:
        for peep in peeps:
            open_prob = update_open_probability(units, open_prob, float(peep), preset, step_duration=step_duration)
            rows.append(simulate_from_probability_state(
                patient,
                VentilatorSettings(float(peep), vt_ml_kg, fio2),
                units,
                open_prob,
                limb,
                step,
                overdistension_penalty=overdistension_penalty,
            ))
            step += 1
    return rows


def scalarize_rows(rows: List[Dict[str, object]]) -> List[Dict[str, float]]:
    scalar_rows = []
    for r in rows:
        scalar_rows.append({k: v for k, v in r.items() if not isinstance(v, np.ndarray)})
    return scalar_rows


def identify_targets(rows: List[Dict[str, object]]) -> Dict[str, float]:
    desc = [r for r in rows if r["limb"] == "descending"]
    by_reg = max(desc, key=lambda r: r["regional_balance_index"])
    by_glob = max(desc, key=lambda r: r["global_balance_index"])
    by_comp = max(desc, key=lambda r: r["compliance_surrogate"])
    by_o2 = max(desc, key=lambda r: r["oxygenation_surrogate"])
    by_spo2 = max(desc, key=lambda r: r["spo2_surrogate"])
    by_dp = min(desc, key=lambda r: r["driving_pressure_surrogate"])
    by_co2 = max(desc, key=lambda r: r["co2_clearance_surrogate"])
    by_co2risk = min(desc, key=lambda r: r["co2_retention_risk"])
    by_gas = max(desc, key=lambda r: r["gas_exchange_balance"])
    return {
        "PEEP_regional_balance": by_reg["PEEP"],
        "PEEP_global_balance": by_glob["PEEP"],
        "PEEP_compliance": by_comp["PEEP"],
        "PEEP_oxygenation": by_o2["PEEP"],
        "PEEP_spo2": by_spo2["PEEP"],
        "PEEP_min_driving_pressure": by_dp["PEEP"],
        "PEEP_co2_clearance": by_co2["PEEP"],
        "PEEP_min_co2_retention_risk": by_co2risk["PEEP"],
        "PEEP_gas_exchange_balance": by_gas["PEEP"],
        "max_regional_balance": by_reg["regional_balance_index"],
        "max_global_balance": by_glob["global_balance_index"],
        "max_compliance": by_comp["compliance_surrogate"],
        "max_oxygenation": by_o2["oxygenation_surrogate"],
        "max_co2_clearance": by_co2["co2_clearance_surrogate"],
        "min_co2_retention_risk": by_co2risk["co2_retention_risk"],
        "max_gas_exchange_balance": by_gas["gas_exchange_balance"],
    }


def extract_map(rows: List[Dict[str, object]], limb: str, peep: float, map_name: str) -> np.ndarray:
    for r in rows:
        if r["limb"] == limb and float(r["PEEP"]) == float(peep):
            return r[map_name]
    raise ValueError(f"No map found for limb={limb}, PEEP={peep}, map={map_name}")
