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




## Cureus revision materials


The following files in `manuscript_supplement/` document the revised manuscript:

- `PRE_Supplementary_Methods_S1.docx`: mathematical specification, parameter and assumption tables, scripted-check classification, and exploratory sensitivity analysis.
- `PRE_v07_exploratory_sensitivity.py`: script that imports the unchanged frozen engine and reproduces the exploratory sensitivity analysis.
- `PRE_v07_exploratory_sensitivity.csv`: tabulated results of the exploratory analyses.
- `README_Cureus_revision_materials.md`: file inventory and reproduction instructions.

These revision materials are separate from the archived v0.7 release. They do not add physiologic validation, parameter calibration, or clinical performance claims.
