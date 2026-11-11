# AI Soccer Agent — Victor_Hyginus

A 5-a-side soccer team written in pure Python (standard library only) for the
Wits **Soccer Agent Challenge**: every team in the class plays every other
team on a live ladder, each decision has a 20 ms deadline, and inside a
division teams are ranked by how *fast* they decide.

The whole team is one file, [`my-team/team.py`](my-team/team.py) (about 2,400
lines). Everything else in this repository is the lab that produced it:
versions v1 to v68, a benchmarking and paired-testing harness, sparring
opponents, and the notes on what was tried and what it measured.

Author: Victor Hyginus

---

## How the team plays

Every tick (20 per second) `act(observation)` decides for all five players.

| Part | What it does |
|---|---|
| **Exact physics** | The ball and player motion are modelled exactly as the engine steps them (friction 0.985 per tick, wall bounces at 0.75, player velocity `0.9 v + move` capped at 8). From that, every player's earliest interception of any ball path is computed with precomputed reach tables. |
| **Learned position value** | What a position is worth was measured, not guessed: an expected-threat grid (chance that the team holding the ball there scores the next goal), learned from hundreds of evenly matched games. |
| **Kick search** | Whoever can kick searches shots, passes, through-balls, carries, dribbles and clearances coarse-to-fine. Each candidate is rolled forward and scored by who reaches it first and where. The search is *anytime*: the candidates that usually win come first, it is capped at 32 evaluations, and a wall-clock guard keeps it inside the deadline. |
| **Learned keep model** | The chance of keeping the ball after a kick is a logistic model fitted on 40,000 logged kicks, re-calibrated against each opponent during the match. |
| **Off the ball** | In attack one player holds back and the others take the spots where they would beat every defender to a pass (pitch control). In defence one covers the ball's route to goal, the rest mark goal-side, and the opponent's next kick is predicted with our own evaluator. |
| **Keeper** | Stands on the bisector of the shooting angle at the depth that best covers both corners; positions come from a table built once at start-up. |
| **Game state** | Shoots more readily when dominating territory or facing a parked bus; from two goals up it lines four players on the goal line and clears (the result is safe and those ticks cost almost nothing to decide). |

## Results

| When | Build | Ladder result |
|---|---|---|
| 22 Oct 2026 | v23 | Division 2, rank 40 (1613-412-255) |
| 23 Oct | v38 era | Division 3, rank 60 of 239, 1.80 ms mean decision |
| 24 Oct | v59 | Division 3, rank 58 of 249, 0.62 ms; completed passes 14 → 20 per match |
| 25 Oct | v66–v68 | 0.50 ms mean decision |
| 28 Oct (final run) | last upload | **Division 6, rank 113 of 280**: 511-259-346, 0.52 ms |

The honest summary: the team got more than three times faster (1.80 → 0.52 ms
per decision) and its early versions reached Division 2, but the rest of the
field improved faster than this approach did, and it finished mid-table. The
notes below record why — most hand-written tactical ideas measured zero
against real opponents, and the few changes that helped were data-driven
(learned values, a refitted risk model) or exact speed-ups.

## What was learned

- **Measure, don't trust.** Self-play between near-equal versions is mostly
  draws; a difference needs hundreds of matches. The lab moved to *paired*
  tests (two versions on identical fixtures, mean difference ± standard
  error). Several ideas passed a 60-match check and then measured zero over
  540 matches.
- **Local opponents saturate.** Once the sparring pool was mostly copies of
  the team itself, it could catch regressions but not find gains. Comparing
  consecutive ladder uploads on opponents who had not changed was far more
  informative.
- **An isolated test can mislead.** A shooting gallery showed an aggressive
  keeper halving goals conceded; on the ladder it conceded *more*, because
  real attackers also pass across the box.
- **Search depth is worth points; search time is not.** Cutting the kick
  search from 32 to 24 evaluations cost 0.16 points per match, and to 16 in
  our own half 0.51. Speed came instead from removing dead work, tables,
  early exits and plan re-use — changes that leave every decision identical
  (checked tick by tick with [`lab/lockstep.py`](lab/lockstep.py)).
- **A selection-biased fit destroys a model.** Refitting the keep model on
  kicks the search had already chosen produced a nearly flat predictor.

The full record, with every number, is in [`notes/plan.md`](notes/plan.md),
[`notes/plan2.md`](notes/plan2.md) and
[`notes/ladder_log.md`](notes/ladder_log.md).

## Repository layout

```
my-team/team.py        the submitted team (final build, v68)
my-team/team.toml      team identity template (placeholder values)
lab/teams/             every version v1 … v68, plus sparring opponents
                       (bus, midtable, selfkeep, sniper, sty_* styles)
lab/make_v*.py         patch scripts that build each version from the last
lab/submitted_*.py     the builds that were uploaded to the ladder
lab/bench.py           team vs opponents over many seeds, in parallel
lab/sweep.py, tune.py  parameter sweeps and a small evolution strategy
lab/paired.py          paired comparison with style metrics
lab/style.py           possession, shots, passes, regain time for a matchup
lab/lockstep.py        tick-by-tick identity check between two builds
lab/speedcmp.py        interleaved decision-time comparison
lab/kickbench.py       deterministic benchmark of the kick search
lab/collect.py, fit.py log kicks and fit the keep / goal models
lab/xt.py              learn the expected-threat grid
lab/gallery.py         shooting gallery for the keeper
lab/eval_*.txt         raw outputs of the experiments quoted in the notes
notes/                 the plan, the research notes and the ladder log
PROJECT_NOTES.md       summary of the assignment rules
```

## Running it

The simulation engine and SDK belong to the course and are **not** included
here. To run anything:

1. Unzip the course distribution (`soccer-student-0.1.0`).
2. Copy this repository's `my-team/`, `lab/` and `notes/` folders into it.
3. From that folder (Python 3.8+, no packages needed):

```bash
python launch.py validate my-team
python launch.py play my-team --against tactical
python lab/bench.py my-team/team.py --vs elite tactical balanced --seeds 1000..1019
python lab/paired.py lab/teams/v66.py lab/teams/v68.py --vs elite lab/teams/selfkeep.py --seeds 7700..7729
```

`lab/kicklog*.json` and `lab/vlog.json` (training logs) are not committed;
rebuild them with `lab/collect.py` and `lab/vlog.py`.

## A note on other teams

Classmates' team names in the notes have been replaced with pseudonyms
(`Team-034` and so on), and no ladder data, replays or student numbers of
other entrants are stored in this repository.
