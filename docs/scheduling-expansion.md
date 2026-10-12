# Further scheduling constructions, 5 September 2026

This records the construction stage. The subsequent all-settings sweep and
current frontier are described in [scheduling-all-settings.md](scheduling-all-settings.md).

This audit starts from the already improved September portfolio. It evaluates
226 shared-hole constructions, 2,648 multiple-point punctures, and 960 bounded
neutral item walks. Independent pair counting validates every accepted cover.
The 79 intermediate improvements leave 69 new nondominated candidates and a
1,119-point frontier across 745 parameter settings.

Compact selections improve in three settings: 51/6 has a better full item-use
profile at the same 90 trials and pair histogram; 75/8 lowers worst-pair
concurrence from 9 to 8 at 105 trials; 100/6 shortens 396 to 352 trials while
increasing worst-pair concurrence from 2 to 12. The last result is a trade-off,
not a simultaneous balance improvement. The earlier 396-trial alternative
remains in the frontier. No connectivity constraint or extra-trial default is
introduced.

With an explicit 25% surplus, 48 selections improve, including 29 trial-count
reductions, 39 full-pair-profile improvements, and nine item-profile improvements
at unchanged trial count and pair profile. Examples: 83/5 falls from 410 to 357
trials; 94/6 and 93/6 each fall from 341 to 304, keeping pair concurrence at most
two. Across modes the improvements concern 50 distinct parameter settings.

`coverlib.expansion` implements three offline candidate generators. With an
outer k-cover on g points, TD(k,n), and an inner k-cover on n+h points, filling
each group together with h common points yields gn+h points and
b_outer*n*n + g*b_inner blocks for 0<h<k. Common-point pair counts add across
the g fillings. This accounts for possible concentration of repeats.

Puncturing retains a selected point set, discards blocks with fewer than two
surviving points, and pads the remaining blocks to k. Every surviving pair
remains covered; duplicate padded blocks can be removed without losing coverage.
Neutral item walks preserve the complete pair histogram and trial count; a
transfer from frequency r to r-1 swaps the two frequencies. They may escape a
strict-improvement local stop. The returned incumbent improves or ties the
input item profile, with no claim of global optimality.

Three integer-programming attempts prescribed a four-point hole in a 20/6
ingredient at 14, 15, and 16 blocks, each with a 45-second limit. All timed out
without a feasible incumbent. They give no infeasibility proof. The residual
solver now correctly labels a truncated enumerated pool as non-exhaustive,
and its documentation explicitly states that None is not an infeasibility
certificate.

The companion paper revision changes scheduling descriptions, the supplementary
balance figure and table, and the finite incidence proof for 16/8. Human data,
estimators, benchmark statistics, and empirical figures are unchanged. The
revision bundle supplies frozen inputs, candidate files, scripts, and hashes;
it is separate from the previously archived public software release.

A subsequent bounded local search improves the 100/6 compact cover at the same
352 trials: worst-pair concurrence falls from 12 to 6, with the full pair profile
strictly improved and every item frequency unchanged. The new validated schedule
replaces the dominated 352-trial point in the manifest; the 396-trial alternative
remains available. The frontier still contains 1,119 points. Searches for an ideal
334-trial cover remain incomplete and establish no infeasibility result.
