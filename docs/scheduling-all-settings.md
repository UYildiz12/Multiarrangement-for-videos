# All-settings scheduling sweep, 5 September 2026

All 745 supported parameter settings were audited against the preceding
1,119-point development frontier. The 259 settings with certified optimal
compact schedules required no further search of the tested objectives. The
remaining 486 settings received 1,230 bounded searches: 578 pair-profile
refinements, 315 item-profile refinements, and 337 one-trial removal attempts.
A follow-up batch ran 274 further searches from promising or improved states.

The final portfolio contains 1,113 nondominated points, including 172 new
candidates across 148 settings. Under the production ranking, 78 compact
selections and 63 selections with an explicit 25% trial surplus improve,
spanning 106 distinct settings. No eligible selection regresses. Balanced mode
still permits zero extra trials by default.

Pair refinement exchanges items between two trials or cycles them among three
trials, preserving every item frequency. Search can temporarily lose coverage;
only complete candidates can enter the portfolio. The best complete descending
pair profile is retained separately from the heuristic search score. Item
refinement preserves the full pair histogram and permits neutral frequency
transfers as well as strict improvements. One-trial removal first restores the
necessary minimum item frequencies, then attempts coverage repair.

The bounded objectives are heuristic. Failure establishes no infeasibility
claim. All retained assignments are checked by independent pair counting, and
all 1,113 published frontier schedules pass the project certificate validator.
The search kernels use the general integer lower bound on pair collisions,
including dense cases whose average concurrence exceeds two.

Examples include:

- 57/7: the balanced choice drops from 98 to 82 trials, retaining maximum
  concurrence 2 and reaching ideal item balance. The 82-trial cover is certified
  optimal for the full compact objective.
- 68/4: the balanced choice drops from 393 to 391 trials, with maximum
  concurrence 2 and every item appearing exactly 23 times. This also certifies
  the full compact optimum.
- 78/8: maximum concurrence falls from 15 to 7 at the same 119 trials.
- 76/9: compact mode falls from 86 to 85 trials, meeting its trial lower bound,
  while maximum concurrence rises from 10 to 11. This is a count-first
  trade-off; the alternative at 86 trials remains available.

The number of compact schedules with certified minimum trial count rises from
408 to 409; the number certified for all compact objectives rises from 259 to
261. Compact mode reaches maximum concurrence at most 3 in 469 settings and
exactly 2 in 246. With the explicit 25% surplus, these counts are 666 and 468.
The most even pair histogram is attained in 314 compact selections and 536
surplus selections. Sixty-eight settings still have exact once-per-pair designs.

The two batches used four single-threaded, below-normal-priority workers for
about 15 minutes of wall time in total. Peak sampled aggregate worker memory
was 80.55 MiB; the Python supervisor and later verification/document work are
additional. The searches finished normally and no background task remains.

The paper changes the frontier counts, scheduling statistics, one concise
method/results paragraph, and the scheduling-balance figure. The representative
table was checked against the new selections and required no numeric changes.
Participant results and the extended empirical supplement remain byte-for-byte
unchanged in the source. The standalone audit bundle provides frozen inputs,
all result witnesses, resource records, the C# kernels and Python runners.
