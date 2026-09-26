# Materials added for the Cureus revision

This folder contains files prepared for the manuscript revision of the Pediatric Recruitment Engine (PRE) technical report.

* `PRE_Supplementary_Methods_S1.docx` contains the mathematical specification, parameter and assumption tables, scripted-check classification, and exploratory sensitivity analysis.
* `PRE_v07_exploratory_sensitivity.py` imports the unchanged frozen PRE v0.7 engine and reproduces the exploratory sensitivity CSV and revised recruitment-hysteresis figure.
* `PRE_v07_exploratory_sensitivity.csv` contains the results of the exploratory one-at-a-time analyses.

The frozen engine itself remains unchanged at commit `7103a11`. These revision materials are separate from the archived v0.7 release and are not evidence of physiologic validation, parameter calibration, or clinical performance.

To reproduce the exploratory analysis from a clone of this repository, install NumPy and Pillow, then run:

```text
python PRE_v07_exploratory_sensitivity.py --engine code/pre_engine_v07.py --out sensitivity_output
```
