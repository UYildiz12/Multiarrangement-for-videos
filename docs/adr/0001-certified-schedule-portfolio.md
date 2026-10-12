# ADR 0001: Monotonic certified schedule portfolio

- Status: accepted
- Date: 2026-07-26

## Context

Multiarrangement has several useful but incomplete sources of schedules:
historical LJCR covers, balanced-search artifacts, exact block designs, nearby
constructions, stochastic local search, and orbit search. No one source covers
the whole supported parameter range, and a bounded search failure is not proof
that a better schedule does not exist.

The runtime also has two distinct concerns. It must choose an unordered block
set with good global pair concurrence, then present those blocks in a useful
order and, for group studies, distribute repeated-pair bias across
participants.

## Decision

Use a monotonic portfolio with four boundaries:

1. `coverlib.certificates` validates candidates and defines the exact compact
   and balanced lexicographic objectives.
2. Construction and search modules produce candidates but never certify their
   own optimality. These include exact/nearby constructions,
   excess-and-leave arithmetic, bounded exact residual completion, cyclic and
   one-rotational search, and fixed-budget local repair.
3. `coverlib.frontier` preserves old artifacts, hash-deduplicates candidates,
   keeps the nondominated `(trial count, concurrence profile)` frontier, and
   publishes a reproducible runtime index.
4. `coverlib.ordering` applies certificate-preserving stimulus relabeling and
   block ordering only after a block set has been selected.

A candidate is stored only after independent validation and a strict exact-key
improvement. Existing files are inputs and are never overwritten or deleted
by regeneration.

The desktop package, public API, and server all consult the same packaged
frontier. Hosted studies cache only the base block set; participant-specific
relabeling and ordering happen after the cache lookup.

## Search-result semantics

- Exhaustive residual failure proves infeasibility only for the fixed core,
  block count, concurrence cap, and fully enumerated candidate universe.
- Beam-pool residual failure is a bounded search miss.
- Cyclic or one-rotational failure concerns only the prescribed automorphisms
  tried within the stated budget.
- Stochastic search failure is a bounded search miss.
- `BEST_FOUND_WITH_GAP` remains attached until arithmetic lower bounds and the
  ideal fixed-budget histogram are both attained.

## Consequences

Adding another construction or search engine cannot make a served schedule
worse under the declared objective. Search campaigns can be stopped, resumed,
or rerun without discarding previous wins. Counterbalancing and trial ordering
improve group-level and anytime behavior while leaving each participant's
global coverage and concurrence certificate unchanged.
