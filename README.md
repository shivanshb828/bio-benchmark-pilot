# Commensurability Pilot

Can a frontier model tell whether two independently reported bioactivity
measurements can legitimately be pooled into one training set?

Merging incompatible assay results is a documented and expensive failure.
Landrum & Riniker found that under minimal curation, almost 65% of same-target
IC50 pairs differ by more than 0.3 log units and 27% by more than one log unit.
A manual re-curation of PDBBind's protein-protein subset found ~19% of records
carried Kd values unsupported by their primary publications, and fixing them
moved a random-forest model's Pearson correlation on log10(Kd) by ~8 points.

Automated systems now generate biological training records at a scale nobody
can hand-verify, and they grade themselves. This pilot asks whether the
underlying judgment call is something models can actually make.

## The trick

The model never sees the measured values. It sees the compound, the target,
and (in Arm B) the two assay protocols, and predicts whether the values will
agree. **Ground truth is free**, because the observed divergence is the label.
No expert panel required.

## Layout

```
src/build_sample.py    build the balanced pair set from ChEMBL32
src/fetch_metadata.py  pull assay descriptions from the ChEMBL API
src/prompts.py         prompt construction + leak guards
src/run_arm.py         run one arm against one model, cached and resumable
src/score.py           metrics, calibration, preregistered decision rule
PREREGISTRATION.md     hypotheses and decision rules, fixed before any run
ATTRIBUTION.md         data provenance and pipeline validation
```

## Run order

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...

python -m src.build_sample                                # already committed
python -m src.run_arm --arm recall  --model claude --limit 30   # contamination
python -m src.run_arm --arm control --model claude        # Arm A, run FIRST
python -m src.run_arm --arm control --model gpt
python -m src.score   --arm control                       # evaluates decision rule

# only if Arm A clears the rule:
python -m src.fetch_metadata
python -m src.run_arm --arm metadata --model claude
python -m src.run_arm --arm metadata --model gpt
python -m src.score   --arm metadata
```

Arm A runs first on purpose. It is the null model: if structure and potency
priors alone predict agreement well, then Arm B is confounded and measures
medicinal chemistry intuition rather than assay reasoning.

## Current state

195 pairs (100 agree, 95 disagree) across 37 targets. IC50 only.
No model has been run yet.
