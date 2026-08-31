# Attribution

`data/source_data/*.IC50.csv.gz` are redistributed unmodified from
<https://github.com/rinikerlab/overlapping_assays> (MIT, © 2023 Greg Landrum),
the companion repository to:

> G.A. Landrum, S. Riniker. "Combining IC50 or Ki Values from Different Sources
> Is a Source of Significant Noise." *J. Chem. Inf. Model.* 2024, 64(5),
> 1560–1567. doi:10.1021/acs.jcim.4c00049

Those files are a "max curation" export of ChEMBL32. ChEMBL is released by
EMBL-EBI under CC BY-SA 3.0.

The upstream MIT license is preserved at `data/LICENSE.overlapping_assays`.

## Reproduction check

Our pairing code reproduces the paper's published max-curation IC50 statistics:

| statistic | published | ours |
|---|---|---|
| pairs differing > 0.3 log units | ~48% | 46.6% |
| pairs differing > 1.0 log units | ~13% | 11.1% |

This is the pipeline validation. If a change to `build_sample.py` moves these
numbers, the change is wrong.
