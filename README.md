# Pediatric Recruitment Engine (PRE) v0.7

This repository contains the frozen source code and generated outputs for the Pediatric Recruitment Engine (PRE), a conceptual and educational computational model for exploring pediatric lung recruitment physiology, hysteresis, and competing PEEP targets.

PRE should not be interpreted as discovering a new physiological relationship. Rather, it provides an inspectable computational representation of established qualitative physiology and allows users to explore how explicit assumptions shape competing PEEP targets.

## Repository structure

```text
code/
  pre_engine_v07.py
  run_pre_v07.py

outputs/
  data/
    Generated CSV and JSON outputs.
  figures/
    Generated figure files.

manuscript_supplement/
  Supplementary_Methods_S1_PRE_v08.docx
  Parameter_Assumption_Justification_PRE_v08.docx
  Parameter_Assumption_Justification_PRE_v08.csv

requirements.txt
```

## Reproducing the outputs

From the repository root:

```bash
python -m pip install -r requirements.txt
python code/run_pre_v07.py
```

On Windows, if `python` is not available but the Python launcher is installed, use:

```bash
py -m pip install -r requirements.txt
py code/run_pre_v07.py
```

The script writes regenerated CSV files and figures to:

```text
outputs/data/
outputs/figures/
```

## Important interpretation note

The model outputs are conceptual and assumption-dependent. CO2-clearance, gas-exchange balance, oxygenation, and related quantities are surrogate indices, not predicted PaCO2, PaO2, SpO2, or clinical outcome measures.

Internal checks are provided to document expected model behavior and code consistency. Passing these checks is not external validation.

## Supplementary methods

Full equations, parameter assumptions, surrogate definitions, sensitivity procedures, and internal evaluation checks are provided in `manuscript_supplement/Supplementary_Methods_S1_PRE_v08.docx`.

The parameter and assumption justification table is provided in both DOCX and CSV formats in `manuscript_supplement/`.

## License

This project is licensed under the Apache License 2.0. See `LICENSE`.
