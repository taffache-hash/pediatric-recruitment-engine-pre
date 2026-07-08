# Pediatric Recruitment Engine (PRE) v0.7

PRE v0.7 is a frozen educational and research simulator of pediatric lung recruitment during PEEP titration. It is not clinical decision-support software, does not predict patient-specific optimal PEEP, and must not be used to guide ventilator settings.

PRE should not be interpreted as discovering a new physiological relationship. Rather, it provides an inspectable computational representation of established qualitative physiology and allows users to explore how explicit assumptions shape competing PEEP targets.

This repository corresponds to the `v0.7-frozen` release.

## Repository structure

```text
README.md
LICENSE
CITATION.cff
requirements.txt

code/
  pre_engine_v07.py
  run_pre_v07.py

manuscript_supplement/
  Supplementary_Methods_S1_PRE_v08.docx
  Parameter_Assumption_Justification_PRE_v08.docx
  Parameter_Assumption_Justification_PRE_v08.csv

outputs/
  v07_primary_targets_default_penalty.csv
  v07_balance_penalty_sensitivity.csv
  v07_severity_targets.csv
  v07_time_dependent_derecruitment_sensitivity.csv
  v07_validation_checks.csv

figures/
  Figure_v07_01_recruitment_hysteresis.png
  Figure_v07_02_co2_clearance_hysteresis.png
  Figure_v07_03_co2_retention_risk.png
  Figure_v07_04_gas_exchange_tradeoff.png
  Figure_v07_05_balance_penalty_sensitivity.png
  Figure_v07_06_severity_targets.png
  Figure_v07_07_derecruitment_sensitivity.png
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
outputs/
figures/
```

## Important interpretation note

The model outputs are conceptual and assumption-dependent. CO2-clearance, gas-exchange balance, oxygenation, and related quantities are surrogate indices, not predicted PaCO2, PaO2, SpO2, or clinical outcome measures.

Internal checks are provided to document expected model behavior and code consistency. Passing these checks is not external validation.

## Supplementary methods

Full equations, parameter assumptions, surrogate definitions, sensitivity procedures, and internal evaluation checks are provided in `manuscript_supplement/Supplementary_Methods_S1_PRE_v08.docx`.

The parameter and assumption justification table is provided in both DOCX and CSV formats in `manuscript_supplement/`.

## License

This project is licensed under the Apache License 2.0. See `LICENSE`.
