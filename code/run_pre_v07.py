
from pathlib import Path
import csv
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pre_engine_v07 import Patient, simulate_protocol, scalarize_rows, identify_targets, extract_map

OUT = Path("outputs")
FIG = OUT / "figures"
DATA = OUT / "data"
FIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

PRIMARY = Patient(age_years=2.0, weight_kg=12.0, label="toddler_2y_moderate", severity="moderate")
SEVERITY_PATIENTS = [
    Patient(age_years=2.0, weight_kg=12.0, label="healthy_2y", severity="healthy"),
    Patient(age_years=2.0, weight_kg=12.0, label="mild_2y", severity="mild"),
    Patient(age_years=2.0, weight_kg=12.0, label="moderate_2y", severity="moderate"),
    Patient(age_years=2.0, weight_kg=12.0, label="severe_2y", severity="severe"),
]
PENALTIES = [1.0, 1.65, 2.5]

def save_csv(rows, path):
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def save_fig(filename):
    plt.tight_layout()
    plt.savefig(FIG / filename, dpi=300)
    plt.close()

def plot_limb(df, metric, ylabel, title, filename):
    plt.figure(figsize=(7.2, 4.8))
    for limb in ["ascending", "descending"]:
        sub = df[df["limb"] == limb]
        plt.plot(sub["PEEP"], sub[metric], marker="o", label=limb)
    plt.xlabel("PEEP (cmH2O)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False)
    save_fig(filename)

def plot_desc_multi(df, metrics, ylabel, title, filename):
    desc = df[df["limb"] == "descending"].sort_values("PEEP")
    plt.figure(figsize=(7.5, 4.8))
    for metric, label in metrics:
        plt.plot(desc["PEEP"], desc[metric], marker="o", label=label)
    plt.xlabel("Descending PEEP (cmH2O)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False)
    save_fig(filename)

# Primary, default penalty
primary_rows = simulate_protocol(PRIMARY, seed=111, overdistension_penalty=1.65)
primary_scalar = scalarize_rows(primary_rows)
save_csv(primary_scalar, DATA / "v07_primary_scalar_default_penalty.csv")
primary_df = pd.DataFrame(primary_scalar)
primary_targets = {"scenario": PRIMARY.label, "penalty": 1.65, **identify_targets(primary_rows)}
pd.DataFrame([primary_targets]).to_csv(DATA / "v07_primary_targets_default_penalty.csv", index=False)

# Balance penalty sensitivity
penalty_rows = []
for penalty in PENALTIES:
    rows = simulate_protocol(PRIMARY, seed=111, overdistension_penalty=penalty)
    save_csv(scalarize_rows(rows), DATA / f"v07_primary_scalar_penalty_{str(penalty).replace('.','_')}.csv")
    penalty_rows.append({"scenario": PRIMARY.label, "penalty": penalty, **identify_targets(rows)})
penalty_df = pd.DataFrame(penalty_rows)
penalty_df.to_csv(DATA / "v07_balance_penalty_sensitivity.csv", index=False)

# Severity sweep
severity_rows = []
for p in SEVERITY_PATIENTS:
    rows = simulate_protocol(p, seed=121, overdistension_penalty=1.65)
    save_csv(scalarize_rows(rows), DATA / f"v07_{p.label}_scalar.csv")
    severity_rows.append({"scenario": p.label, "severity": p.severity, **identify_targets(rows)})
severity_df = pd.DataFrame(severity_rows)
severity_df.to_csv(DATA / "v07_severity_targets.csv", index=False)

# Derecruitment kinetics: step duration sensitivity
derec_rows = []
for step_duration in [0.5, 1.0, 2.0]:
    rows = simulate_protocol(PRIMARY, seed=131, step_duration=step_duration, overdistension_penalty=1.65)
    scalar = pd.DataFrame(scalarize_rows(rows))
    asc = scalar[(scalar["limb"] == "ascending") & (scalar["PEEP"] == 12)]
    desc = scalar[(scalar["limb"] == "descending") & (scalar["PEEP"] == 12)]
    mem = float(desc["recruited_fraction"].iloc[0] - asc["recruited_fraction"].iloc[0])
    derec_rows.append({"step_duration": step_duration, "memory_effect_at_PEEP_12": mem, **identify_targets(rows)})
pd.DataFrame(derec_rows).to_csv(DATA / "v07_time_dependent_derecruitment_sensitivity.csv", index=False)

# Validation checks
desc = primary_df[primary_df["limb"] == "descending"].sort_values("PEEP")
asc = primary_df[primary_df["limb"] == "ascending"].sort_values("PEEP")
tests = []
def add_test(test_id, category, description, passed, value, criterion):
    tests.append({
        "test_id": test_id,
        "category": category,
        "description": description,
        "passed": bool(passed),
        "observed_value": value,
        "criterion": criterion,
    })

add_test("V07-T01", "code", "No NaN in scalar outputs", not primary_df.select_dtypes(include=[np.number]).isna().any().any(), "", "No numeric NaN")
add_test("V07-T02", "face", "Recruitment increases with PEEP", asc["recruited_fraction"].iloc[-1] > asc["recruited_fraction"].iloc[0], f"{asc['recruited_fraction'].iloc[0]:.3f}->{asc['recruited_fraction'].iloc[-1]:.3f}", "High PEEP > low PEEP")
add_test("V07-T03", "face", "Collapse decreases with PEEP", asc["collapsed_fraction"].iloc[-1] < asc["collapsed_fraction"].iloc[0], f"{asc['collapsed_fraction'].iloc[0]:.3f}->{asc['collapsed_fraction'].iloc[-1]:.3f}", "High PEEP < low PEEP")
add_test("V07-T04", "face", "Overdistension increases with high PEEP", asc["overdistended_fraction"].iloc[-1] > asc["overdistended_fraction"].iloc[0], f"{asc['overdistended_fraction'].iloc[0]:.3f}->{asc['overdistended_fraction'].iloc[-1]:.3f}", "High PEEP > low PEEP")
add_test("V07-T05", "construct", "Time-dependent hysteresis gives matched-PEEP memory effect", float(desc[desc['PEEP']==12]['recruited_fraction'].iloc[0] - asc[asc['PEEP']==12]['recruited_fraction'].iloc[0]) > 0.05, f"{float(desc[desc['PEEP']==12]['recruited_fraction'].iloc[0] - asc[asc['PEEP']==12]['recruited_fraction'].iloc[0]):.3f}", ">0.05")
add_test("V07-T06", "construct", "CO2 clearance is nonmonotonic and peaks away from highest PEEP", desc.loc[desc["co2_clearance_surrogate"].idxmax(), "PEEP"] < desc["PEEP"].max(), f"peak PEEP {desc.loc[desc['co2_clearance_surrogate'].idxmax(), 'PEEP']:.0f}", "< maximum tested PEEP")
add_test("V07-T07", "construct", "Oxygenation target remains above regional balance target", primary_targets["PEEP_oxygenation"] > primary_targets["PEEP_regional_balance"], f"O2={primary_targets['PEEP_oxygenation']}; balance={primary_targets['PEEP_regional_balance']}", "O2 PEEP > regional balance PEEP")
add_test("V07-T08", "robustness", "Regional balance target remains below oxygenation across all balance penalties", (penalty_df["PEEP_oxygenation"] > penalty_df["PEEP_regional_balance"]).all(), str(list(zip(penalty_df["penalty"], penalty_df["PEEP_regional_balance"], penalty_df["PEEP_oxygenation"]))), "All penalty settings")
add_test("V07-T09", "robustness", "Gas-exchange balance target does not default to highest PEEP", primary_targets["PEEP_gas_exchange_balance"] < 24, f"{primary_targets['PEEP_gas_exchange_balance']}", "< 24")
add_test("V07-T10", "construct", "Severity increases regional-balance PEEP", all(x <= y for x,y in zip(severity_df["PEEP_regional_balance"], severity_df["PEEP_regional_balance"].iloc[1:])), str(list(severity_df["PEEP_regional_balance"])), "nondecreasing")
test_df = pd.DataFrame(tests)
test_df.to_csv(DATA / "v07_validation_checks.csv", index=False)

# Figures
plot_limb(primary_df, "recruited_fraction", "Recruited fraction", "v0.7 recruitment with time-dependent derecruitment", "Figure_v07_01_recruitment_hysteresis.png")
plot_limb(primary_df, "co2_clearance_surrogate", "CO2 clearance surrogate", "CO2 clearance surrogate during PEEP protocol", "Figure_v07_02_co2_clearance_hysteresis.png")
plot_limb(primary_df, "co2_retention_risk", "CO2 retention risk surrogate", "CO2 retention risk surrogate during PEEP protocol", "Figure_v07_03_co2_retention_risk.png")
plot_desc_multi(primary_df, [
    ("oxygenation_surrogate", "Oxygenation surrogate"),
    ("co2_clearance_surrogate", "CO2 clearance surrogate"),
    ("gas_exchange_balance", "Gas-exchange balance"),
], "Scaled/surrogate output", "Oxygenation and CO2-clearance targets diverge", "Figure_v07_04_gas_exchange_tradeoff.png")

plt.figure(figsize=(7.3, 4.8))
plt.plot(penalty_df["penalty"], penalty_df["PEEP_regional_balance"], marker="o", label="Regional balance")
plt.plot(penalty_df["penalty"], penalty_df["PEEP_oxygenation"], marker="o", label="Oxygenation")
plt.plot(penalty_df["penalty"], penalty_df["PEEP_gas_exchange_balance"], marker="o", label="Gas-exchange balance")
plt.xlabel("Overdistension penalty weight")
plt.ylabel("Model-derived PEEP (cmH2O)")
plt.title("Balance-index penalty sensitivity")
plt.grid(True, alpha=0.25)
plt.legend(frameon=False)
save_fig("Figure_v07_05_balance_penalty_sensitivity.png")

plt.figure(figsize=(7.3, 4.8))
plt.plot(severity_df["severity"], severity_df["PEEP_regional_balance"], marker="o", label="Regional balance")
plt.plot(severity_df["severity"], severity_df["PEEP_co2_clearance"], marker="o", label="CO2 clearance")
plt.plot(severity_df["severity"], severity_df["PEEP_oxygenation"], marker="o", label="Oxygenation")
plt.xlabel("Conceptual impairment preset")
plt.ylabel("Model-derived PEEP (cmH2O)")
plt.title("Target PEEP shift across impairment presets")
plt.grid(True, alpha=0.25)
plt.legend(frameon=False)
save_fig("Figure_v07_06_severity_targets.png")

derec_df = pd.DataFrame(derec_rows)
plt.figure(figsize=(7.3, 4.8))
plt.plot(derec_df["step_duration"], derec_df["memory_effect_at_PEEP_12"], marker="o")
plt.xlabel("Protocol step-duration surrogate")
plt.ylabel("Matched-PEEP memory effect at PEEP 12")
plt.title("Time-dependent derecruitment sensitivity")
plt.grid(True, alpha=0.25)
save_fig("Figure_v07_07_derecruitment_sensitivity.png")

# Summary JSON
summary = {
    "primary_targets": primary_targets,
    "validation_passed": int(test_df["passed"].sum()),
    "validation_total": int(len(test_df)),
    "penalty_sensitivity": penalty_df.to_dict(orient="records"),
    "severity_targets": severity_df.to_dict(orient="records"),
}
(DATA / "v07_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("PRE v0.7 refined engine run complete.")
print("Validation:", int(test_df["passed"].sum()), "/", len(test_df))
print("Primary targets:")
print(pd.DataFrame([primary_targets]).to_string(index=False))
print("\nPenalty sensitivity:")
print(penalty_df[["penalty", "PEEP_regional_balance", "PEEP_oxygenation", "PEEP_gas_exchange_balance"]].to_string(index=False))
print("\nValidation checks:")
print(test_df[["test_id", "passed", "observed_value"]].to_string(index=False))
