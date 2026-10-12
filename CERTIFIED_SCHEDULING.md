# Certified scheduling

The active objective is compact and balanced complete coverage, with no
connectivity constraint. Production balanced mode allows zero extra trials by
default. The September 2026 refinements and proofs are documented in
[`docs/compact-balanced-design.md`](docs/compact-balanced-design.md).

The latest all-settings audit validates 1,113 frontier points for 745 settings.
Relative to the preceding development cache, 78 compact selections and 63
optional 25%-surplus selections improve, spanning 106 settings. There are now
261 settings with a certified full compact optimum. The audit and its trade-offs
are documented in [`docs/scheduling-all-settings.md`](docs/scheduling-all-settings.md).
These computational scheduling results are separate from the participant
benchmark. The preceding construction audit remains documented in
[`docs/scheduling-expansion.md`](docs/scheduling-expansion.md).

The scheduler treats every available schedule as a candidate in a portfolio.
Existing LJCR seeds, prior balanced-search results, deterministic
constructions, and bounded search are complementary; adding a construction
does not delete or overwrite an earlier result.

## Objective order

Compact mode compares complete covers lexicographically by:

1. number of trials;
2. the full pair-concurrence vector, sorted largest first;
3. the full item-use deviation vector.

Balanced mode compares complete covers by:

1. the full pair-concurrence vector, sorted largest first;
2. number of trials;
3. the full item-use deviation vector.

This replaces threshold decisions such as accepting a normalized ratio of
`1.5`. Normalized metrics remain useful diagnostics, but they do not decide
optimality.

## Deterministic portfolio

`coverlib.constructions` supplies:

- exact Steiner triple, projective-plane, and affine-plane designs;
- one-point extensions of supported exact designs;
- one-point truncations of supported exact designs.

An exact design or one-point extension is used as a compact fast path only when
its block count attains the Schonheim lower bound. Truncations and all other
structured candidates enter the balanced portfolio and must win the same exact
comparison as cached and searched schedules.

The complete search portfolio is layered:

- `coverlib.excess` derives the sparse excess or leave graph and tests the
  degree-congruence and graphicality conditions for an ideal fixed-budget
  schedule;
- `coverlib.residual` fixes most blocks and exactly completes or replaces a
  small tail under a hard concurrence cap;
- `coverlib.symmetry` searches cyclic and one-rotational orbit cores and can
  hand their free tail to the residual solver;
- `coverlib.balanced` supplies bounded fixed-budget swap search;
- `coverlib.campaign` runs these stages over the repository cache and writes
  only independently certified strict improvements;
- `coverlib.frontier` preserves the nondominated trial-count/concurrence
  frontier and publishes `multiarrangement/frontier_cache/index.json`.

The architecture decision and failure semantics are recorded in
[`docs/adr/0001-certified-schedule-portfolio.md`](docs/adr/0001-certified-schedule-portfolio.md).

## Certificates

`coverlib.certificates.certify_schedule` validates block size, item range,
simplicity, and complete pair coverage. It records the schedule hash, lower
bound, pair and item histograms, full comparison profiles, and only statuses
that are mechanically justified:

- `MINIMUM_TRIALS_CERTIFIED` means a complete cover attains the arithmetic
  lower bound;
- `IDEAL_HISTOGRAM_AT_B` means the pair-concurrence histogram is the most even
  integer histogram possible at that fixed trial count;
- `PAIR_PROFILE_AT_B_CERTIFIED` recognizes either the ideal histogram or a
  proved structural optimum, including the supported six-trial incidence cases;
- `PARETO_CERTIFIED` requires minimum trials and a certified best pair profile
  at that trial count;
- `LEXICOGRAPHIC_OPTIMUM_CERTIFIED` additionally requires ideal item exposure;
- `BEST_FOUND_WITH_GAP` is used for a valid complete schedule without a proof
  of both properties.

The certificate hash is invariant to block order and within-block order. It is
not an isomorphism certificate under arbitrary stimulus relabeling.

## Incremental guarantees

The old cache remains available as input to the portfolio. A new candidate is
selected only when it is better under the declared objective, so deterministic
work improves or ties the existing result rather than resetting the search.
The adaptive LTW scheduler remains separate and unchanged.

Cache readers reject repeated items and repeated blocks before optimization.
The audit removed the pre-existing `v100_k8_t2.txt` placeholder because it
contained only one malformed block; it was not a valid covering result.

The first deterministic-construction audit found 16 improved parameter pairs.
After two cache-wide bounded search passes, the final 2026-07-26 audit compares
the complete portfolio with the untouched LJCR and balanced caches across all
745 stored parameter pairs:

- compact mode strictly improves 30 parameter pairs and removes 16 trials in
  total;
- balanced mode strictly improves 66 parameter pairs and removes 117 trials in
  total;
- the union is 66 unique `(v, k)` pairs: 16 construction wins and 50 additional
  bounded-search wins;
- balanced mode lowers `lambda_max` from 3 to 2 in 11 pairs and improves the
  full concurrence profile in 43 more pairs whose `lambda_max` remains 3.

The machine-readable audit is
[`search_reports/portfolio_audit.json`](search_reports/portfolio_audit.json).
Examples include `(v, k) = (50, 7)`, `(58, 8)`, `(74, 9)`, `(82, 9)`, and
new searched wins such as `(97, 9)`, `(89, 10)`, and `(69, 9)`.

General covering search is still combinatorially hard. Certificate checking,
exact comparisons, and the supported construction families are inexpensive;
uncovered parameter families continue to rely on the existing cache and
bounded search.

## Participant presentation

The 2026-09-05 update adds transversal inflation, reuse of cached Steiner
ingredients, and pair-histogram-preserving item trades. Against the frozen
pre-update portfolio of 745 parameter settings, compact/default balanced mode
improves 41 settings and removes 45 trials in aggregate across the benchmark.
The separately evaluated 25%-extra budget improves 77 settings; 83 settings
improve in at least one of these modes. In particular, (100,4) improves from
850 to the proved minimum of 825 trials, and (100,5) improves from 525 to 505
without a minimum-trial claim. All eight (2k,k) cases for k=3..10 now receive
full compact-optimality certificates from the finite incidence bound.

The selected unordered schedule is then prepared independently:

- deterministic relabeling families flatten aggregate concurrence bias across
  participants without changing any participant-level certificate;
- deterministic trial ordering improves item balance and pair coverage in
  early prefixes, reduces long item gaps and adjacent overlap, and can smooth
  trial duration when clip durations are known.

Hosted set-cover studies enable both by default. They can be controlled with
`counterbalance_schedules`, `counterbalance_family_size`, and
`optimize_trial_order`. The public Python API exposes the corresponding
keyword arguments.
