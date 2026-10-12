# Compact and balanced initial designs

The active scheduling objective is complete pair coverage with as few trials as
possible, followed by the most even achievable pair repetition and stimulus
exposure. The intended measurement model assumes a common arena-based scale.
No connectivity constraint or calibration-trial surcharge is imposed. The
earlier trial-scale calibration experiment has been removed from the project;
its historical research bundle remains separate. The independent SMACOF
correction and its geometry tests are retained.

## What is minimized

Write v for the stimulus count, k for the fixed trial size, b for the number of
trials, lambda_ij for pair concurrence, and r_i for item frequency. Coverage
requires lambda_ij >= 1. Compact mode orders complete candidates by b, then the
descending concurrence vector, then the descending absolute item-deviation
vector. Balanced mode compares concurrence first within an explicit trial
budget. The production default allows zero extra trials. An optional 25%
allowance is a separate benchmark and is not a change to this default.

Counting pair observations gives

\[
E=\sum_{i<j}(\lambda_{ij}-1)=b\binom{k}{2}-\binom{v}{2}.
\]

At fixed b and k, total repetition E is fixed. Refinement improves its
distribution. Reducing b reduces total repetition. Shared-pair graph component
count is reported only as a diagnostic: it is not an additional objective.

Every item must appear at least ceil((v-1)/(k-1)) times. Summing item incidences
gives the Schönheim lower bound. All production copies now calculate its two
ceilings using integers. The old floating-point expression incorrectly returned
491 at (98,5), even though a valid 490-trial cover was already available.

## Transversal inflation

Suppose an outer complete cover has g points and block size k, an inner complete
cover has n points and block size k, and TD(k,n) exists. Replace each outer point
by a group of n items. For every outer block, use the n^2 transversal rows to
cover every between-group pair. Place a copy of the inner cover inside every
group. Then

\[
v=gn,\qquad b=b_{\mathrm{outer}}n^2+g b_{\mathrm{inner}}.
\]

Between-group concurrence equals the corresponding outer pair concurrence;
within-group concurrence equals inner concurrence. Item frequency is
n*r_outer[group] + r_inner[item]. Consequently exact ingredients yield exact
pair coverage and equal item exposure. The pair histogram can also be predicted
exactly by multiplying the outer histogram's frequencies by n^2 and adding g
copies of the inner histogram.

`coverlib.recursive` constructs transversal rows over supported finite fields
and their direct products. Arithmetic modulo a composite integer is not used
as a substitute for a field. The module also extends or truncates any verified
Steiner ingredient from the cache, beyond the families recognized by the
original built-in constructor. This is an implementation of established
recursive design methods, not a claim to have invented transversal designs.

For (100,4), use a 25-point, 50-block exact outer design and a four-point inner
block: 50*16+25=825 trials, every pair once, every item 33 times. The counting
bound is attained. For (100,5), use five groups of 20 with a 21-trial inner
cover: 400+5*21=505 trials. This has 4,850 pairs once, 100 twice, and item
frequencies 25 or 26. Its lower bound is 500, so minimum trial count is not proved.

## Item balancing with the pair histogram fixed

Consider replacing x by y in trial {x} union S, where y is absent from that
trial. For each z in S, lambda_xz decreases by one and lambda_yz increases by
one. The entire pair-concurrence histogram is preserved if and only if

\[
\{\!\{\lambda_{xz}:z\in S\}\!\}
=\{\!\{\lambda_{yz}+1:z\in S\}\!\}.
\]

To see necessity as well as sufficiency, let A_t and C_t be the multiplicities
of t in those two multisets. The histogram change at t is
(A_{t+1}-C_{t+1})-(A_t-C_t). If every change is zero, A_t-C_t is constant; its
finite support forces that constant to be zero. Because the schedule is
complete, every term on the right is at least two, so no removed pair loses
its last observation.

Requiring r_x >= r_y+2 makes the change in item sum of squares equal to
-2(r_x-r_y-1), strictly negative. It also improves the sorted absolute-deviation
profile by transferring one incidence from a more frequent to a less frequent
item. `coverlib.refinement.improve_item_balance` applies only such moves, rejects
duplicate blocks, and independently certifies its output. A seed changes only
the internal traversal order. The bounded search is a local method and does not
prove global nonexistence when it stops.

The campaign includes an `items` stage even when pair counts are already ideal.
The public cover API also refines item use and protects the incumbent's full
compact objective from a regression by the older local optimizer.

## A stronger finite optimality certificate

For v=2k, k>=3, a complete six-trial cover forces every item to occur in exactly
three trials: coverage requires at least three, and the total is 6k=3v.
Represent an item by its three-trial support. There are 20 possible supports,
partitioned into ten complementary pairs. Two complementary supports cannot
both occur, since those items would never meet. Hence at most ten distinct
supports can occur.

Identical supports produce concurrence three. If 2k=10q+s with 0<=s<10, convex
counting forces at least 10*binom(q,2)+s*q such pairs. At equality the ten support
multiplicities must be q or q+1. We exhaust every equality case by assigning
the larger multiplicities and checking all 2^10 complementary orientations
against the six required column sums k. This rules out equality for k=4,6,9.
Existing complete witnesses attain the next integer in those three cases.

| k | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|
| Minimum pairs with concurrence 3 | 0 | 1 | 0 | 3 | 4 | 6 | 9 | 10 |

There can be no concurrence above three. Once the number of triplicate pairs
is fixed, pair and observation totals determine the numbers occurring once and
twice. Thus this proves the full best concurrence profile at six trials, not
only its maximum. Equal item exposure is forced, and six trials attain the
trial lower bound. The eight witnesses are therefore globally optimal under
the compact lexicographic objective. This finite derivation uses elementary
incidence duality and exhaustive equality checks; no literature-novelty claim
is made. The proof is reproduced in `tests/test_incidence_bounds.py` and its
frozen witness fixture.

`SIX_TRIAL_INCIDENCE_OPTIMUM` applies only to the stated eight parameter pairs
at b=6. `PAIR_PROFILE_AT_B_CERTIFIED` recognizes either this bound or an attained
arithmetic ideal histogram. `PARETO_CERTIFIED` combines a minimum-trial proof
with a best pair profile at that b. `LEXICOGRAPHIC_OPTIMUM_CERTIFIED` additionally
requires the ideal item profile. These statuses do not certify optimality for
a different trial budget or a different statistical estimation objective.

## Literature and the next generalization

The general existence theory explains why exact designs are possible for
sufficiently large admissible sizes. Its pairwise case is Wilson's theorem;
Keevash's general theorem and subsequent absorption proofs cover broader
design problems. They do not provide an immediately usable optimum generator
for every small parameter pair. See [Keevash's 2024 shorter proof](https://arxiv.org/abs/2411.18291).

For the finite sizes here, the most practical continuation is a larger library
of group-divisible and incomplete designs with small residual problems.
[Chee, Colbourn, Ling and Wilson (2013)](https://web.spms.ntu.edu.sg/~ccrg/documents/covpack.pdf)
show that fixed-k pair coverings can stay within an additive constant of the
basic lower bound for sufficiently large v. Their use of small holes motivates
this direction, without proving that our finite residual searches will succeed.
