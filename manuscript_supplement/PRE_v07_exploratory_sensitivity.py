"""Read-only exploratory sensitivity analysis of the frozen PRE v0.7 engine.

The frozen engine is imported without modification. Each scenario uses the
same 2-y, 12-kg conceptual example and seed 111. Ranges are illustrative,
not confidence or pediatric physiologic intervals.
"""

from __future__ import annotations

from dataclasses import replace
import argparse
import csv
import importlib.util
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--engine", type=Path,
                    default=Path(__file__).resolve().parent / "code" / "pre_engine_v07.py",
                    help="Path to the unchanged frozen PRE v0.7 engine")
parser.add_argument("--out", type=Path, default=Path.cwd(),
                    help="Directory for the CSV, figure, and a copy of this script")
args = parser.parse_args()
ENGINE = args.engine.resolve()
OUT = args.out.resolve()
if not ENGINE.is_file():
    parser.error(f"Frozen engine not found: {ENGINE}. Pass --engine explicitly.")
spec = importlib.util.spec_from_file_location("pre_engine_v07", ENGINE)
pre = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pre
spec.loader.exec_module(pre)

PATIENT = pre.Patient(2.0, 12.0, "toddler_2y_moderate", "moderate")
PEEPS_UP = list(range(0, 25, 2))
PEEPS_DOWN = list(range(24, 1, -2))


def run_with_units(units: dict[str, np.ndarray], *, step_duration: float = 1.0,
                   balance_penalty: float = 1.65) -> list[dict[str, object]]:
    state = pre.initialize_open_probability(units)
    rows = []
    step = 0
    for limb, pressures in (("ascending", PEEPS_UP), ("descending", PEEPS_DOWN)):
        for peep in pressures:
            state = pre.update_open_probability(
                units, state, float(peep), pre.PRESETS["moderate"], step_duration
            )
            rows.append(pre.simulate_from_probability_state(
                PATIENT, pre.VentilatorSettings(float(peep), 6.0, 0.60),
                units, state, limb, step, balance_penalty
            ))
            step += 1
    return rows


def run_preset(field: str, value: float) -> list[dict[str, object]]:
    old = pre.PRESETS["moderate"]
    try:
        pre.PRESETS["moderate"] = replace(old, **{field: value})
        return pre.simulate_protocol(PATIENT, seed=111)
    finally:
        pre.PRESETS["moderate"] = old


def run_reweight(field: str, tilt: float) -> list[dict[str, object]]:
    units = pre.generate_regional_lung_units(PATIENT, seed=111)
    centered_row = units["row"].astype(float) / 3.0 - 0.5
    units[field] = units[field] * np.exp(tilt * centered_row)
    units[field] = units[field] / units[field].sum()
    return run_with_units(units)


def outcome(rows: list[dict[str, object]], group: str, value: float) -> dict[str, object]:
    t = pre.identify_targets(rows)
    asc = next(r for r in rows if r["limb"] == "ascending" and r["PEEP"] == 12)
    desc = next(r for r in rows if r["limb"] == "descending" and r["PEEP"] == 12)
    return {
        "group": group,
        "value": value,
        "regional_balance_target_cmH2O": t["PEEP_regional_balance"],
        "gas_exchange_target_cmH2O": t["PEEP_gas_exchange_balance"],
        "co2_clearance_target_cmH2O": t["PEEP_co2_clearance"],
        "oxygenation_target_cmH2O": t["PEEP_oxygenation"],
        "matched_PEEP_12_recruitment_difference":
            float(desc["recruited_fraction"] - asc["recruited_fraction"]),
        "regional_below_oxygenation":
            t["PEEP_regional_balance"] < t["PEEP_oxygenation"],
    }


records = []
base = pre.simulate_protocol(PATIENT, seed=111)
records.append(outcome(base, "baseline", 0.0))

for group, field, values in (
    ("mean_opening_pressure_cmH2O", "mean_opening_pressure", (8.0, 10.0, 12.0)),
    ("mean_hysteresis_gap_cmH2O", "mean_hysteresis_gap", (3.0, 4.0, 5.0)),
    ("overdistension_shift_cmH2O", "overdistension_shift", (9.5, 11.5, 13.5)),
    ("derecruitment_rate_per_step", "derecruitment_rate", (0.15, 0.30, 0.45)),
):
    for value in values:
        records.append(outcome(run_preset(field, value), group, value))

for group, field in (
    ("perfusion_dependent_tilt", "perfusion"),
    ("ventilation_dependent_tilt", "ventilation_weight"),
):
    for value in (-0.5, 0.0, 0.5):
        records.append(outcome(run_reweight(field, value), group, value))

for value in (1.0, 1.65, 2.5):
    records.append(outcome(
        pre.simulate_protocol(PATIENT, seed=111, overdistension_penalty=value),
        "overdistension_balance_penalty", value
    ))

# Post hoc alternative weighting of the two existing gas-exchange ingredients.
# This does not alter PRE v0.7 or its reported default index.
descending = [r for r in base if r["limb"] == "descending"]
for oxygenation_power in (0.5, 1.0, 1.5):
    best = max(descending, key=lambda r: (r["oxygenation_surrogate"] / 100.0)
               ** oxygenation_power * r["co2_clearance_surrogate"]
               ** (2.0 - oxygenation_power))
    records.append({
        "group": "posthoc_gas_exchange_oxygenation_power",
        "value": oxygenation_power,
        "regional_balance_target_cmH2O": "",
        "gas_exchange_target_cmH2O": best["PEEP"],
        "co2_clearance_target_cmH2O": "",
        "oxygenation_target_cmH2O": "",
        "matched_PEEP_12_recruitment_difference": "",
        "regional_below_oxygenation": "",
    })

OUT.mkdir(parents=True, exist_ok=True)
destination = OUT / "PRE_v07_exploratory_sensitivity.csv"
with destination.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, records[0].keys())
    writer.writeheader()
    writer.writerows(records)

for record in records:
    print(record)
print(f"WROTE {destination}")

# Replot the identical frozen baseline data with direction made explicit.
asc_plot = sorted((r for r in base if r["limb"] == "ascending"), key=lambda r: r["PEEP"])
desc_plot = sorted((r for r in base if r["limb"] == "descending"), key=lambda r: r["PEEP"])
image = Image.new("RGB", (2100, 1400), "white")
draw = ImageDraw.Draw(image)
def font(size: int, *, bold: bool = False):
    candidates = (
        [r"C:\Windows\Fonts\arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
        else [r"C:\Windows\Fonts\arial.ttf", "DejaVuSans.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


title_font = font(53, bold=True)
body_font = font(35)
small_font = font(30)
axis_font = font(39)
left, right, top, bottom = 230, 2010, 270, 1220
blue, orange = "#2474b5", "#e6791c"

def xy(peep: float, fraction: float) -> tuple[int, int]:
    return (round(left + (right-left) * peep/24),
            round(bottom - (bottom-top) * fraction/1.05))

draw.text((left, 45), "Recruitment hysteresis during a simulated PEEP sequence", font=title_font, fill="#111111")
draw.text((left, 122), "Model output; pressure steps are sequential, not calibrated to elapsed time", font=body_font, fill="#444444")
for fraction in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
    y = xy(0, fraction)[1]
    draw.line((left, y, right, y), fill="#dfe3e7", width=2)
    draw.text((left-100, y-23), f"{fraction:.1f}", font=small_font, fill="#222222")
for peep in range(0, 25, 2):
    x = xy(peep, 0)[0]
    draw.line((x, top, x, bottom), fill="#ebedef", width=2)
    draw.text((x-18, bottom+16), str(peep), font=small_font, fill="#222222")
draw.line((left, top, left, bottom), fill="#111111", width=4)
draw.line((left, bottom, right, bottom), fill="#111111", width=4)

def draw_series(rows: list[dict[str, object]], color: str, marker: str) -> None:
    coords = [xy(float(r["PEEP"]), float(r["recruited_fraction"])) for r in rows]
    draw.line(coords, fill=color, width=7, joint="curve")
    for x, y in coords:
        if marker == "circle":
            draw.ellipse((x-11,y-11,x+11,y+11), fill=color)
        else:
            draw.rectangle((x-10,y-10,x+10,y+10), fill=color)

draw_series(asc_plot, blue, "circle")
draw_series(desc_plot, orange, "square")

def arrow(start: tuple[float,float], end: tuple[float,float], color: str) -> None:
    x1,y1 = xy(*start)
    x2,y2 = xy(*end)
    draw.line((x1,y1,x2,y2), fill=color, width=11)
    vec = np.array([x2-x1,y2-y1], dtype=float)
    vec = vec / np.linalg.norm(vec)
    perp = np.array([-vec[1],vec[0]])
    tip = np.array([x2,y2], dtype=float)
    base = tip-37*vec
    wing1 = base+18*perp
    wing2 = base-18*perp
    draw.polygon([tuple(tip),tuple(wing1),tuple(wing2)], fill=color)

arrow((8.2,0.11),(10.7,0.23),blue)
arrow((17.2,0.99),(14.5,0.95),orange)
draw.line((left+35,top+38,left+115,top+38), fill=blue, width=7)
draw.ellipse((left+65,top+27,left+87,top+49), fill=blue)
draw.text((left+130,top+15), "Ascending sequence: 0 to 24 cm H2O", font=body_font, fill="#202020")
draw.line((left+35,top+93,left+115,top+93), fill=orange, width=7)
draw.rectangle((left+65,top+82,left+87,top+104), fill=orange)
draw.text((left+130,top+70), "Descending sequence: 24 to 2 cm H2O", font=body_font, fill="#202020")
draw.text((960, 1290), "PEEP (cm H2O)", font=axis_font, fill="#111111")
y_label = Image.new("RGBA", (900, 70), (255,255,255,0))
ImageDraw.Draw(y_label).text((0,0), "Model-derived recruited fraction", font=axis_font, fill="#111111")
y_label = y_label.rotate(90, expand=True)
image.paste(y_label, (18, round((top + bottom - y_label.height) / 2)), y_label)
figure_path = OUT / "Figure_1_revised_recruitment_hysteresis.png"
image.save(figure_path, dpi=(300,300))
print(f"WROTE {figure_path}")
analysis_script = OUT / "PRE_v07_exploratory_sensitivity.py"
if Path(__file__).resolve() != analysis_script.resolve():
    shutil.copy2(Path(__file__), analysis_script)
print(f"WROTE {analysis_script}")
