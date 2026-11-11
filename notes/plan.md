# Plan: Victor_Hyginus → Division 1 (points) with a 4–6x faster decision

Written 2026-10-23 against the live ladder (run started 17:15 UTC, 239 teams,
916 matches each on seeds 1000–1003, both ends) and the code in
`my-team/team.py` (v51). Everything below was measured, not assumed; the
numbers are quoted so the plan can be re-checked when the ladder moves.

---

## 0. Where we actually are (ladder, 2026-10-23)

| | Victor_Hyginus (rank 60, Div 3) | Div 1 floor (rank 20 on points) | Div 1 typical (top 10) |
|---|---|---|---|
| Points | **2067** (643-138-135) | **≈2391** | 2430–2630 |
| Goals for / match | 2.70 | — | 3.7–5.3 (Team-225/Team-106 are 1.0 with 27% territory: pure counter teams) |
| Goals against / match | 0.33 | — | 0.05–0.5 |
| Mean decision (server) | **1.80 ms**, 332 timeouts | — | **0.10–0.75 ms** (rank inside a division = decision time) |

Divisions are the top 20 / next 20 / ... **on points**; inside a division the
order is **mean decision time**. So points get us into Div 1, decision time
decides where in it we sit. We need **≈ +330 points** from 916 matches.

### Where the points are lost (our 916 matches, bucketed by opponent rank)

| Opponent rank | W-D-L | GF-GA | Points | Max possible | Gap |
|---|---|---|---|---|---|
| 1–20 | 3-10-67 | 28-145 | 19 | 240 | 221 |
| 21–40 | 18-27-35 | 47-72 | 81 | 240 | 159 |
| 41–80 | 75-55-26 | 140-58 | 280 | 468 | 188 |
| 81–150 | 228-45-7 | 512-28 | 729 | 840 | 111 |
| 151+ | 319-1-0 | 1743-1 | 958 | 960 | 2 |

92 of our 138 draws are 0-0. **The arithmetic is brutal: even winning every
single match against ranks 41+ (+299) is not quite enough on its own; Div 1
needs near-perfection against ranks 41–150 plus a real step forward against
21–40.** That is what the top-10 do (Team-189: 862-35-19).

### What the replays say (our own matches, read in the browser, faithful ones only)

*Replay team index = `header.team_ids` order, not `recorded.teams`.*

1. **0-0 vs Team-109 (rank 45–90, seed 1001).** We had 74% territory
   but only **2% of ticks in their final 15 units with the ball, 3 "shots", all
   from 36–38 units** against a keeper standing 1.5 units off his line (every
   one saved/blocked within 5 ticks). Their four outfielders sat at
   x = 8–25 in our attacking half (a mid-block), |y| 8–15. 50 of our 120
   kicks were sub-0.3-power safe-dribble touches that went nowhere. **This is
   the draw machine**: territory without penetration. Our local proxy
   `lab/teams/midtable.py` is beaten 30-0-0 — it is far too weak to represent
   these teams.
   *Correction after re-reading the replay with the right team index:* the
   74% territory came with only **39% possession** — they held the ball 61%
   of the match *in their own half* with small touches (50 of their 169
   kicks under 0.3 power). So the 0-0s are the same disease as the top-team
   defeats: we cannot win the ball back from a carrier. Phase D matters for
   the mid-table too, and the proxies are built as ball-keepers
   (`lab/teams/keepball.py`, `block.py`, `dribbler.py`).
2. **0-4 vs Team-248 (rank 7, seed 1000).** They had **85% possession,
   183 kicks to our 12**. 80 of their touches were power < 0.3 (dribbling
   with the ball at their feet; ball mostly at 6–16 u/s), possessions of
   30+ consecutive kicks, their keeper sits **10 units off his line** as a
   sweeper, and they keep the ball in *their own half* (outfield mean x
   −13…+3) until a pass opens a shot from 19–32 units: 4 goals from 4
   attempts, ball arriving at 18–25 u/s with our keeper 3–8 units out and
   beaten to the corner. Our intercept model assumes a free-rolling ball, so
   against a carrier who re-touches every 3–5 ticks we never get it back.
3. Timeouts: 332 on the ladder. Our kick-tick budget is 11 ms *server* time,
   plus post-budget work; on the ~2.5x slower server a kick tick averages
   ~9.5 ms and the tail crosses 20 ms.

### Where the decision time goes (local, v51 vs elite, seed 1002: mean 0.71 ms)

| Tick type | Share of ticks | Mean | Share of time |
|---|---|---|---|
| kick decision (`choose_kick`) | 7% | 3.8 ms | 39% |
| off-ball, attacking | 59% | 0.48 ms | 39% |
| off-ball, defending | 34% | 0.46 ms | 22% |

cProfile (3.4 s total): `support_plan` 1.18 s (of which `pc_assign` 0.84 s,
268k `reach_est` calls) · `evaluate` 0.93 s (13.7k calls, ~68 µs each) ·
`anticipate` 0.37 s · `first_intercept` 0.33 s (10 players every tick) ·
**`score_spots` 0.31 s — dead work: `support_plan` recomputes it every 3
ticks and then takes the `pc` branch that never reads it** · `keeper_spot`
0.23 s (an iterative search re-run every tick for a function of two inputs).
Server factor ≈ 2.5 (0.71 local → 1.80 ladder).

---

## 1. Targets and gates

| Target | Now | Gate before upload |
|---|---|---|
| Points | 2067 | Local gauntlet (section 5) predicts ≥ +250; ladder confirms |
| vs mid-block proxy (`block.py`, new) | unknown (expect many 0-0) | ≥ 26-4-0 over 30, ≥ 2.5 goals/match |
| vs dribbler proxy (`dribbler.py`, new) | unknown (expect heavy losses) | not worse than 10-10-10 |
| vs v38cap / v48cap | 13-17-0 / ~ | no regression (≥ 12 wins, ≤ 2 losses) |
| Mean decision, local | 0.71 ms | **≤ 0.18 ms** (→ ≈ 0.45 ms server, mid-Div-1) |
| p99 / max, local | 4.9 / 6.3 ms | ≤ 2 / ≤ 5 ms (zero server timeouts) |
| `validate` + `check` | pass | pass twice in a row |

Decision-time work is sequenced *first* because every later tactical change
is then measured at the speed it will really run at (the v23 lesson: search
quality collapses when the server truncates it, so a plan tuned at full speed
is a lie).

---

## 2. Phase A — decision time: 0.71 → ≤ 0.18 ms local (2–3 days)

Each step is bit-identical or gated by `lab/kickbench.py` (identity + speed)
and a 30-match `bench.py` vs v38cap. Keep `max_evals` 32 as the server
equivalent.

### A1. Off-ball ticks 0.47 → ≤ 0.08 ms (this is 61% of all time)

1. **Delete the dead `score_spots` call** in `support_plan` when `pc` is on
   (−0.13 ms/tick on attacking ticks). Zero behaviour change — *verified*:
   `lab/teams/v51_a1.py` is this one change; `lab/lockstep.py` (new: feeds
   both teams the same observations and compares every action) reports 0
   differing player-actions over 2400 ticks, and `lab/phase_timing.py` (new)
   shows the off-ball tick cost falling as expected.
2. **`keeper_spot` lookup table.** The spot depends only on the threat point
   (tx, ty) and fixed params. Lazily fill a 2-unit grid (50×30 cells, our
   half mirrored in y) on first use; bilinear read thereafter. −0.09 ms/tick.
   Gate: `lab/keeper_test.py` unchanged save rate.
3. **Pitch-control cadence.** `pc_assign` evaluates 81 spots × 5 defenders ×
   up to 4 free men every 3 ticks. Change to: recompute when the predicted
   holder changes or every 6 ticks, otherwise re-use targets; prune spots
   whose `pos_value` is below the current best for that man (spots sorted by
   value once); evaluate defenders with `reach_est` only for the 3 nearest to
   the spot. Target −0.2 ms/tick.
4. **Intercept lower bound.** For the 10 `first_intercept` calls per tick,
   first compute the free-ball distance lower bound (`dmin − r − drift`)/0.4
   and skip any player whose bound exceeds the best tick so far (same trick
   `evaluate` already uses). −0.05 ms/tick.
5. **Ball-path reuse.** The free-ball path is deterministic: if this tick's
   ball velocity equals last tick's predicted velocity (no kick, no
   collision), reuse last tick's `pts[1:]` instead of rebuilding 80 points.
6. **`anticipate` only when it can matter**: opponent receiving within 6
   ticks *and* a free defender exists *and* the receiver is in our half.

### A2. Kick ticks 3.8 → ≤ 1.5 ms

1. **Budget to 5 ms** (server time; the guard is wall-clock) and move the
   post-budget lookahead (`la_k`) inside the budget. Kills the 332 timeouts.
2. **Scan only who matters.** Build `_theirs_t`/`_mine_t` once per kick
   decision sorted by distance, and let `evaluate` stop after the 3 nearest
   opponents and 3 nearest teammates unless the lower bound says a farther
   player could still be first. Gate with kickbench identity (expect >95%
   identical decisions).
3. **Cheaper safe-dribble screen**: the 12-heading loop calls `reach_ticks`
   (iterative) per opponent; switch to the closed-form `reach_est` first and
   confirm with `reach_ticks` only when the margin is within 2 ticks of
   `sd_safe`.
4. **Candidate ordering from a distilled model (the big one, A3).**

### A3. Search distillation (lets us go below 0.1 ms later if wanted)

Log (state features → family/angle/speed chosen by the full search) over
~40k decisions with `lab/collect.py`; fit a small multinomial logistic model
(pure Python, like `lab/fit.py`) that predicts the *family and coarse angle*
of the winning kick. At run time evaluate the model's top-3 candidates
first; if the best of them clears a value margin over the others, stop at
~6 evaluations instead of 32. Expected: kick tick ≈ 0.8 ms, no quality loss
in the 80% of "obvious" decisions, full search kept for the rest. This is
the same shape as RoboCup's learned pass generators (SPO: one forward pass
replaces repeated evaluator calls, ~3x faster).

Expected end of Phase A: local mean ≈ 0.08 + 0.07 × 1.2 ≈ **0.16 ms**,
server ≈ 0.4 ms, which would rank us ~12th of the current Div 1 on time.

---

### Phase A status (2026-10-23)

Done as v53 (exact) + v54 (approximate), now in `my-team/team.py`:
local production mean **0.42 ms** (v51: 1.02 ms, same seeds, interleaved
timing), max ≈ 6 ms, validate 0.44 ms. Strength unchanged or better: 553 vs
553 points over 240 matches (pool + proxies), 185 vs 169 over 120 matches vs
v48cap/v38cap. Expected server mean ≈ 0.8–1.0 ms (from 1.80). Not yet done:
A2.2/A2.3 (kick-evaluator pruning) and A3 (distillation) — kick ticks are
now ~40% of the time.

## 3. Phase B — measurement that matches the ladder (1 day, in parallel)

Our local pool says 30-0-0 vs "midtable" while the ladder says 0-0; the pool
is blind to the two things that cost us most. Build two archetypes from what
the replays show (behaviour only, derived from our own matches):

1. **`lab/teams/block.py`** — the mid-table shape that draws 0-0 with us:
   keeper on the line tracking the ball's y (depth ≤ 2); four outfielders
   holding a line `x = clamp(ball_x − 14, 5, 25)` (in their attacking frame)
   at |y| ≈ 8 and 14, stepping out to a ball within 6 units, the nearest man
   pressing the carrier, long clearances to the wings under pressure, shots
   only inside 25. Calibrate against the replay numbers above (their 4 men at
   x 8–25, us at 74% territory / 2% final-third).
2. **`lab/teams/dribbler.py`** — the top-team style: our own engine with the
   safe-dribble enabled everywhere (`sd_xmin −50`), a sweeper keeper at depth
   8–10, passes only when the dribble margin drops, shots inside 25. Target:
   85% possession against v51, as Team-248 has.
3. **Ladder replay sampler (browser-side, aggregate stats only).** A page
   script that samples ~40 of our faithful replays and prints per match:
   territory, final-third share, shots and their distance, our keeper depth
   at each conceded goal, carrier-touch share. This is the dashboard every
   upload is judged on, alongside the rank buckets. (Replays are 8 MB each;
   one per call, nothing saved to disk.)

New gauntlet = `block`, `dribbler`, `v38cap`, `v48cap`, `bus`, `elite`, 30
seeds each, `max_evals` 32 + the real-deadline run with 4 workers.

---

## 4. Phase C — penetration against mid-blocks: the +200-point item (3–4 days)

Hypothesis (from replay 1): we lose nothing in our half and win nothing in
theirs because against a block at x 8–25 the kick evaluator finds no
candidate worth more than a safe sideways touch, and when it finally shoots
it is from 37 units into a keeper who has 27 ticks to cover 7 units.

### C1. Runner behind the line (third-man / through-ball pattern)

* **Positioning.** When their deepest outfield defender is at x ≥ 5 and
  their keeper depth ≤ 3, assign one supporter the *break spot*: 6–8 units
  behind their line, on the far side from the ball, chosen so that `tthem −
  tus` is maximised for a ball played at 14–18 u/s. Today `pc_assign` already
  scores such spots but gives defenders zero reaction delay, so they always
  look covered. Add a **defender reaction delay** (defenders do not move until
  the ball is struck; measured from replays ≈ 3–5 ticks) to the pitch-control
  model and keep it as a tuned parameter.
* **The kick.** `c_through` (8 units ahead) and `c_leads` already generate
  the ball; raise their weight in the anytime order when the break spot
  exists, and value the reception with the first-time-shot lookahead
  (`shot_value_from`) against the keeper's *actual* position — a 1v1 at
  x ≈ 38 against a line keeper is worth ≈ 0.7 goals, far above the 0.13–0.37
  the XT grid gives that cell.
* **Timing.** The runner starts when the carrier commits (the carrier's
  dribble heading points at the gap); `arrive_gain` 2.5 already produces
  the sprint.

### C2. Cut-back finish (how the top teams score)

Their goals: byline run to (40–47, ±8–16), ball across to a man at (42, ∓5),
first-time 30 u/s strike from 8–10 units. We have the pieces (`box_on`,
`la_ys`, `sd_shot`) but only in dominance mode and without a dedicated
candidate. Add a **cut-back candidate family**: when the carrier is at x >
36 and |y| > 7, pass targets at the box man's position plus leads, valued
by `shot_value_from` with the keeper's true position and the defenders'
head start. Gate: goals/match vs `block.py`.

### C3. Shot discipline

Shots from > 30 units against a keeper within 2 units of his line have a
measured value near zero and hand the ball back (3 of 3 in replay 1). Make
`shot_range` keeper-aware: effective range = 24 + 1.5 × keeper depth
(a sweeper at depth 10 can be beaten from 39; a line keeper only from ~25),
and inside the range prefer the dribble-then-shoot sequence (`sd_shot`) over
the immediate strike when the dribble margin ≥ 3 ticks.

### C4. Kickoff set play

After every goal we concede we get 59 unopposed ticks with the ball on the
spot and every opponent outside the circle; the server ignores formations,
so both sides start in the engine defaults. Design one rehearsed restart:
first touch back to the second man at the circle edge, two runners already
sprinting wide as the restart expires, long switch into the channel behind
their line. Measure goals within 200 ticks of our kickoffs vs `block.py`.
Cheap to build, directly converts 0-0s.

Expected: 41–150 bucket from 303-100-33 towards ≥ 400-30-6 (≈ +250 points).

---

## 5. Phase D — winning the ball back from dribblers (2–3 days)

Hypothesis (replay 2): 12 kicks in 2400 ticks because the chaser runs to the
free-ball intercept point of a ball that is never free.

1. **Carrier model.** When an opponent has control (within kick range and
   touched the ball in the last 6 ticks), predict the ball as *moving with
   the carrier* at his heading and ≤ 8 u/s, not as a free roll. Chaser target
   = the point on the carrier's path we reach first, approached from the
   goal side so his only free heading is backwards.
2. **Contain + lane press.** Second defender takes the carrier's best pass
   lane (we already run their kick search in `anticipate`; reuse its best
   candidate instead of marking goal-side), third defender covers the
   through-ball behind. Our keeper drops to depth ≤ 3 when the carrier is
   inside 30 units (their 18–25 u/s shots beat a keeper standing 6–8 out:
   every one of Team-248's four goals).
3. **Evaluate on `dribbler.py` only** — v43 tried pressing against
   non-dribbling proxies and measured nothing; that is a measurement failure,
   not evidence against pressing.

Expected: 21–40 bucket from 18-27-35 towards 30-30-20 (+50), and fewer heavy
defeats to the top 20 (goal difference is the tie-break).

---

## 6. Phase E — keep calibrating with the ladder (ongoing)

* After each upload: pull the bucket table and the replay dashboard; the
  ladder re-runs within ~2 minutes of an upload (run 17:15:24 → 17:16:43).
* Re-fit `KEEP_W` on logged kicks that include `block`/`dribbler` opponents
  (the current fit never saw a mid-block or a dribbler).
* Keep `lab/submitted_v38.py` and `lab/submitted_candidate_v50.py` as
  fallbacks; the current ladder entry (1.80 ms, 2067 pts) is the baseline.

---

## 7. Order of work and expected value

| Step | Effort | Points | Decision time | Risk |
|---|---|---|---|---|
| A1 off-ball speed (dead work, tables, cadence) | 0.5 day | 0 | −0.35 ms local | none (bit-identical where claimed) |
| A2 kick-tick speed + 5 ms budget | 0.5 day | +5 (no timeouts) | −0.15 ms | low (kickbench identity) |
| B proxies + replay dashboard | 1 day | 0 (enables everything) | — | — |
| C1–C3 penetration vs blocks | 3 days | **+150 to +250** | +0.02 ms | medium: must not revive the "passive vs bus" regression (check `bus.py`) |
| C4 kickoff set play | 0.5 day | +20 to +40 | 0 | low |
| D carrier model + press | 2 days | +40 to +80 | +0.03 ms | medium |
| A3 distillation | 1.5 days | 0 | −0.5 ms on kick ticks | medium |

Total if C and D both land: ≈ 2330–2430 points, i.e. the Div 1 floor, at
≈ 0.4–0.5 ms server time. Anything less than the full C programme leaves us
in Div 2. That is the honest size of the gap.

---

## 8. Things already tried that this plan deliberately does *not* repeat

Hand-set sigmoid tuning, idle-tick planning, early refine, hard passes,
fixed attacking shape, re-learned XT grid, defensive distance sweeps, more
search compute (64 / unlimited evals vs v38: 13-15-2 / 6-20-4 — the model,
not the search, is the limit), safe-dribbling in our own half (retreats and
concedes). See the lab notes in memory for the numbers.

## 9. Housekeeping before any upload

* `my-team/team.toml` still says `name = "My Team"`, `student_number =
  "2412345"` — fill in the real name and student number or the submission is
  not marked.
* Run `START.cmd validate my-team` then `START.cmd check` twice (the first
  run occasionally reports 1–2 stall spikes under load).

## 10. Additions after the Phase A results (2026-10-23, evening)

What Phase A taught, and what it changes in the plan above.

### 10.1 The proxies must be *accepted* against replay statistics, not written and hoped for

`keepball`/`block`/`dribbler` lose ~30-0-0 to v54, so they measure nothing.
A proxy is only usable once it reproduces what the ladder team does *to us*.
Acceptance test for each proxy (30 matches vs v54, `max_evals` 32):

| Proxy | Must reproduce (from our replays) | Current |
|---|---|---|
| block (mid-table 0-0 teams) | our possession ≤ 45%, our shots ≤ 5/match, ≥ 30% of matches 0-0 | we win 30-0-0 |
| dribbler (top-20 style) | their possession ≥ 70%, their kicks ≥ 8× ours, ≥ 20 consecutive touches per possession | we win 30-0-0 |

Two ways to get there, try in this order:
1. **Self-play proxy.** The strongest ball-keeper we own is our own engine:
   `v54` with `sd_xmin −50` (safe-dribble everywhere), `sd_fwd` lowered,
   `shot_range` 24, keeper depth 8–10 via `home_x`/`gk_max`, and the
   `reuse_k` tricks off. Cheap to build (a parameter file through
   `lab/sweep.py`'s template), and already plays the physics exactly.
2. **Imitation from replays.** For the mid-block teams, fit each defender's
   target position as a linear function of ball (x, y) from our own replays
   (aggregate coefficients only, computed in the browser; nothing saved
   but the fitted numbers), and the keeper's y-tracking gain. Same for the
   carrier's touch rule (speed vs nearest-defender distance). Then the proxy
   is *their* positioning with our kick physics.

Until a proxy passes its acceptance test, no Phase C/D result counts.

### 10.2 One metric for Phase D: regain time

Add to `lab/bench.py` (and the browser replay sampler): **mean ticks from an
opponent possession starting to our next touch**, and the share of opponent
possessions longer than 100 ticks. Vs Team-248 that share is ~100%; vs the
local pool it is near 0. Phase D's gate is this number against the accepted
dribbler proxy, not W-D-L (which is too coarse at 30 matches).

### 10.3 Opponent-style detection online (the ladder has four styles)

The replays separate the field into styles we can detect inside a match
from signals we already compute: their keeper's depth, their touch-power
distribution (share of kicks < 0.3), their outfield line when we have the
ball, our possession share. Map them to parameter sets the way `dom_mode`
and `bus_mode` already do:

| Style | Signal | Response |
|---|---|---|
| Ball-keeper (top 20) | they keep ≥ 65% possession in the first 400 ticks, touches < 0.3 | Phase D press set; keeper depth ≤ 3 |
| Mid-block | their line at x 5–25 when we have the ball, keeper on the line | Phase C runner/cut-back set, `shot_range` 24 |
| Sweeper keeper | their keeper depth ≥ 6 | shoot early from 30–40 on any regain (the goal is open behind him) |
| Rusher/bus | existing `bus_mode` detection | unchanged |

This generalises the dominance/bus modes that gave +100 ladder points on
their own (v34 → v38), and it is cheap: one EMA per signal.

### 10.4 Use the ladder as the experiment, deliberately

An upload is re-scored across 916 matches in under two minutes, on the four
fixed seeds the ladder uses — a far better instrument than 30 local matches.
Sequence uploads so each answers one question:

1. **v54 now** (same decisions as v51 modulo the approximations): measures
   the server speed factor cleanly (expect 1.80 → ~0.9 ms) and whether the
   332 timeouts vanish. Also tells us whether v50/v51's attacking changes
   (never uploaded) help against real mid-table teams.
2. Then one tactical change per upload, reading the bucket table
   (`api/team`) each time. Keep a log in `lab/ladder_log.md`: version, points,
   W-D-L, mean ms, bucket table.

Because the seeds are fixed, two uploads differing by a tiny change can flip
dozens of individual matches; judge buckets, not single results.

### 10.5 Decision time, what is left

Kick ticks are now 40% of the time (2.5–3.0 ms each, 7% of ticks). The
`validate` run still shows a 10.5 ms slowest decision, which is a kick tick
on a loaded machine. Remaining steps, in order of payoff: A2.2 nearest-only
scanning inside `evaluate` (expect −30% per kick tick), A2.3 closed-form
dribble screen, then A3 distillation. Target after these: mean ≤ 0.25 ms
local, slowest ≤ 4 ms. Also recalibrate the server factor from the v54
upload before quoting server numbers again.

### 10.6 Risks added to the register

* The ladder's four fixed seeds mean our result against any one opponent is
  almost deterministic; local 30-match tests on random seeds smooth over
  this. Always test on seeds 1000–1003 *as well as* random ones.
* Plan re-use (`reuse_k` 3) is a behaviour change under one condition: a
  team-mate who could kick next tick is checked, but an *opponent* about to
  kick is not — if an opponent kicks between full ticks, the ball leaves the
  predicted path and re-use stops the following tick. One tick of stale
  steering; measured as harmless, but revisit if Phase D's press looks slow
  to react.

## 11. Status after Phase B and the first Phase D test (2026-10-23, night)

* **B done except B3** (browser replay sampler). `lab/style.py` measures
  possession, shots, regain time and 0-0 share. Hand-written proxies
  failed acceptance; **`lab/teams/selfkeep.py`** (v54 dribbling everywhere,
  shooting from inside 26) passes as the ranks-41–80 proxy: v54 gets 41%
  possession, 5 shots/match, 8-6-2. Making it hold the ball longer
  (`sd_bonus` up) made it *weaker*, so a top-20 proxy cannot come from
  self-play; it would have to come from imitation (10.1 route 2).
* **Second presser: no effect.** Looked +20–30 points over 120–300 matches,
  then −24 over a 180-match decider. Dropped.
* **Noise is the binding constraint**: ±25 points per 180 matches. From now
  on a change is accepted only on ≥ 500 matches, or on the ladder.

## 12. Additions after Phase B and the pressing test

### 12.1 A measurement protocol, because noise is now the main obstacle

The pressing test flipped sign between 300 and 480 matches. Points over
independent match sets have a spread of about ±25 per 180 matches; most of
the gains we are hunting are smaller than that. Three changes:

1. **Paired tests.** Both variants play the *same* seeds against the same
   opponents from the same ends, and the statistic is the per-match
   difference (goal difference, then points). Pairing removes the
   seed-to-seed variance, which is most of the noise. `lab/sweep.py` already
   plays identical fixtures for every variant; add a `--paired` report that
   prints mean difference ± standard error per opponent.
2. **Continuous gates before W-D-L.** Goals for per match, shots per match,
   regain time and possession (all from `lab/style.py`) have far lower
   variance than points. A Phase C change must first move *goals for* vs
   `selfkeep` (now 1.19/match) and *shots* (5.0/match); a Phase D change must
   first move *regain time* (108 ticks) and *their long possessions* (63%).
   Only a change that moves its mechanism metric goes on to a 500-match
   points test.
3. **Stop rule.** No decision on fewer than 500 paired matches unless the
   paired difference exceeds 3 standard errors earlier.

### 12.2 What the pressing result says about Phase D

Adding a second body to the press did not reduce the opponent's possession
against `selfkeep` in any run (their long-possession share stayed
~60–65%). The ball is not won by numbers; it is won by being where the
carrier's *next touch* lands. So Phase D is rewritten around the carrier
model (D1) and nothing else is tried until D1 exists:

* When an opponent is within kick range of the ball and moving with it,
  predict the ball as the carrier's position plus his heading × touch
  speed (the `selfkeep`/top-team touch is 7–12 u/s along a free heading),
  re-planned every tick, and send the chaser to the point on *that* path he
  reaches first, from the goal side.
* Gate: regain time vs `selfkeep` from 108 ticks towards ≤ 70, long
  possessions from 63% towards ≤ 40%, before any points test.

### 12.3 What `selfkeep` says about our own tactics

Making the proxy hold the ball longer (`sd_bonus` 0.8–1.5) raised its
possession to 65–76% and made it *lose more*. Possession without
penetration is worthless in this engine, which is also the lesson of our
own 74%-territory 0-0s. So Phase C's success metric is goals, never
possession or territory, and the dominance mode's territory EMA should be
re-checked: it may be rewarding exactly the wrong thing.

### 12.4 Phase C now has a usable target

`selfkeep` draws 6 of 16 with v54 and limits us to 5 shots/match, so it is
the right opponent for C1–C3 (runner behind the line, cut-back family,
keeper-aware shot range). Order: C3 first (cheapest, and it removes the
wasted 37-unit shots), then C1, then C2. Each gated on goals/match and
shots/match vs `selfkeep` under the paired protocol.

### 12.5 The top-20 proxy must come from imitation

Self-play cannot produce a Team-248: our engine gets weaker the more it is
told to keep the ball, because its value function does not know how to
turn possession into shots the way the top teams do. Build the imitation
proxy from our own replays against top-20 teams (browser-side, aggregate
coefficients only): each outfielder's target as a linear function of the
ball's position and the carrier's position, the keeper's depth rule, and
the carrier's touch rule (heading = freest direction, speed by nearest
defender distance, pass when the margin is below a threshold, shoot inside
~25). Acceptance: ≥ 70% possession vs v54, kicks ≥ 5× ours.

### 12.6 Ladder log

Start `lab/ladder_log.md` with the current entry (v38-era build: 2067
points, 643-138-135, 1.80 ms, 332 timeouts, bucket table in section 0) and
add one row per upload. The v54 upload is the next row and answers the
server speed factor and the timeout question before any tactical upload.

## 13. D1 and C3 results under the paired protocol (2026-10-23)

Tool: `lab/paired.py` (B − A on identical fixtures, mean ± standard error;
A_P/B_P overrides). Experiments live in `lab/teams/v55.py` behind switches
that default off (v55 == v54, lockstep 0 diffs).

| Test | Matches | Result | Verdict |
|---|---|---|---|
| D1 carrier model, car_t 3 / 6 | 60 vs selfkeep | their long possessions **+6.8 / +9.0 pp**, our possession −3.3 / −3.7 pp, goals for +0.08 / −0.23 | **rejected**: chasing the carrier's projected position lets him turn away more easily than chasing the ball's path |
| C3 shot range 24 + 1.5·depth / 27 + 1.0·depth | 60 vs selfkeep | goals for +0.37 ± 0.16 / +0.35 ± 0.12 | passed the gate… |
| C3 27 + 1.0·depth | **540, whole pool, fresh seeds** | points **−0.01 ± 0.04**, goals for −0.03 ± 0.04; vs selfkeep +0.03 ± 0.10; vs elite −0.29 ± 0.14 | **rejected**: the gate was a fluke |

Lessons for the protocol:

* A 60-match gate at "3 standard errors" still produced a false positive.
  Gates now need a *second, independent* seed set before the 500-match
  test, and the 500-match test is the only one that decides.
* The paired 540-match test resolves ±0.04 points per match, i.e. ±35
  ladder points over 916 matches. That is the smallest effect we can see
  locally; anything smaller needs the ladder.
* Three reasonable local changes in a row (second presser, carrier chase,
  shot range) have measured zero. The engine's search already plays these
  situations about as well as these heuristics can; the plan's remaining
  bets need either a model the evaluator lacks (body-blocking of touches,
  the defender reaction delay of C1) or imitation of the top teams (12.5).

## 14. Reassessment after three null results

### 14.1 What has ever moved the ladder, and what has not

| Changed the ladder | Measured zero locally |
|---|---|
| Learned position value from data (XT grid, v15–v23) | second presser |
| Learned keep model from 40k logged kicks (v47–v48) | carrier chase (D1) |
| Opponent modes: bus mode, dominance mode (+101 pts, v34→v38) | keeper-aware shot range (C3) |
| Search order under truncation (v32) | distance/shape sweeps, hard passes, pressing dribblers (v42–v44) |
| Speed (v54: same decisions, 2.4× faster) | |

Every win came from *data* or from *detecting the opponent*; every hand-made
tactical rule has measured zero. The plan should weight the remaining work
accordingly.

### 14.2 Nearest realistic goal: Division 2, ranked high on speed

The Div 2 floor is ≈ 2125 points; we have 2067 — **+58 points**, inside the
resolution of a single good change. Inside Div 2 the order is decision time,
and v54 at ≈ 0.9 ms server would already sit mid-table there; finishing A2/A3
(≤ 0.4 ms) would put us near the top of Div 2. Div 1 (+330) stays the aim,
but the next upload should be judged against the Div 2 line.

### 14.3 Re-ordered bets

1. **Refit the keep model with ball-keepers in the pool** (data route, the
   one that has worked twice). `lab/collect.py` with `selfkeep` added to POOL,
   `lab/fit.py`, then a 540-match paired test. The current KEEP_W never saw
   a team that dribbles, which is exactly where our risk estimates are wrong.
2. **Finish decision time** (A2.2, A2.3, A3): certain gain in rank inside
   whatever division we land in; no tactical risk.
3. **Opponent-style detection** (10.3) with the parameter sets we already
   have: the mechanism with the best ladder record. Needs the ladder to
   evaluate (local pool has one style), so it goes out as its own upload.
4. **C1 with a defender reaction delay** — the one tactical idea that adds a
   missing *model* rather than a rule (defenders cannot react before the
   kick; the evaluator currently gives them zero delay). Gate on goals vs
   `selfkeep`, second seed set, then 540 paired.
5. **Imitation proxy of the top 20** (12.5) — needed before anything aimed at
   ranks 1–40 can be measured.

Dropped from the active list: more pressing variants, more shot-range or
distance rules, anything whose only argument is "it looks sensible".

### 14.4 Pool saturation

In the 540-match test our hardest opponents were our own recent versions
(1.24 points/match vs v48cap, 1.52 vs v38cap) while `selfkeep` (2.37) and
`elite` (2.89) are easy. The pool is dominated by near-copies of ourselves,
so it rewards changes that beat *us* and is blind to changes that beat the
ladder. Keep v38cap/v48cap as regression guards only; weight decisions on
`selfkeep`, `bus`, `elite` and, once it exists, the imitation proxy.

### 14.5 Time-boxing

Each local bet gets one gate + one 540-match test (≈ 1.5 hours of compute).
If it does not clear, it is written up in section 13's table and dropped —
no second round of parameter tweaks on a null result.

## 15. Bet 1 result: keep-model refit with selfkeep in the pool — rejected

Data: `lab/collect.py v55` (now takes `--pool`), 480 matches vs selfkeep,
v38cap, v48cap, v3, bus, elite, midtable, v1 → 38,802 logged kicks
(`lab/kicklog55.json`), exploration ε 0.15 among the top 6 candidates.

* The current KEEP_W is only mildly miscalibrated on this data (predicted
  0.874 → actual 0.840; 0.906 → 0.933).
* The refit is **nearly flat**: it predicts 0.86 for 98.5% of kicks. The
  logged kicks are the ones the search already chose, so margin, speed and
  distance barely vary in the data; a fit on them throws the
  discrimination away (selection bias).
* Paired gate vs selfkeep, 60 matches (seeds 8000–8029):

| Variant | Points | Goal diff | Verdict |
|---|---|---|---|
| v56a full refit | **−0.65 ± 0.16** | −0.42 ± 0.20 | rejected (4 SE worse) |
| v56b 50/50 blend with the v48 fit | −0.20 ± 0.15 | −0.03 ± 0.18 | rejected |

What would make a refit valid (a new bet, not a retry): collect with
exploration over the *whole* candidate list (ε ≈ 0.5, uniformly among all
evaluated kicks, in separate exploration-only matches so the losses don't
matter), so that low-margin and high-speed kicks appear in the data; fit on
that plus the existing 40k rows; and weight rows by inverse selection
probability. Until then KEEP_W stays as in v48.

## 16. Bet 2 result: decision time (2026-10-23)

* **A2.2 was already in place.** `evaluate` sorts players by a distance lower
  bound and stops once no farther player can arrive first; there is nothing
  left to prune exactly.
* **The search is not converged** (`lab/evalcurve.py`, 260 captured kicks):
  vs the 32-evaluation pick, 24 evaluations agree 85%, 16 agree 61%, and 48
  agree only 64%. choose_kick costs 0.71 ms at 8 evaluations (fixed cost:
  dribble screen and shot lookaheads) to 1.75 ms at 32.
* **A3 (distillation) dropped.** With 36% of picks changing between 32 and
  48 evaluations, there is no stable "winning family" to distil; cutting
  evaluations is the only form of it, and that was tested directly.
* **Exact savings → v57, installed.** Mode parameter sets cached; opponent
  bodies built only on full ticks. Lockstep 0 diffs vs v54 on two seeds;
  off-ball 0.248 → 0.240 ms (small). Validate mean 0.55 ms on a loaded
  machine, slowest 7.8 ms; `check` passed twice after one load spike.
  v54 saved as `lab/submitted_candidate_v54.py`.
* **Approximations rejected** (540 paired matches each):

| Variant | Local mean | Points/match | vs selfkeep | Verdict |
|---|---|---|---|---|
| reuse_k 5 + max_evals 24 | 0.31 → 0.25 ms | −0.02 ± 0.06 | +0.19 ± 0.16 | goals −0.06 ± 0.05: not worth the risk |
| reuse_k 5 alone | 0.33 → 0.30 ms | −0.04 ± 0.06 | **−0.43 ± 0.15** | rejected |

Where decision time now stands: ≈ 0.31–0.36 ms local on a quiet machine
(kick ticks ≈ 2.3 ms × 5%, off-ball ≈ 0.24 ms × 95%); expected ≈ 0.8 ms on
the server. Further cuts need cheaper *off-ball* logic (it is now ~70% of
the time), and every cheaper variant tried so far has cost points against
the ladder-like proxy. Decision time is parked until a ladder run gives the
real server factor.

## 17. v57 on the ladder, and the passing gap (2026-10-23, 20:13 run)

**Result.** 2036 points from 948 matches (2.148/match, was 2.257), 0.78 ms
(was 1.80), 48 timeouts (was 332), rank 58, Div 3. Speed landed as
predicted (server ≈ 2.2× local). Points fell by about 100 on a like field;
0-0 draws rose from 92 to 129 and goals for fell from 2.70 to 2.36 per
match, mostly against the bottom of the table (5.45 → 4.75).

**Cause found.** The production guard was cut from 11 ms to 6 ms in v54.
At the server-equivalent local budget, 26% of kick searches stop short and
some get zero evaluations (the fallback is a blind full-power kick forward).
Every local test since v54 ran without a guard, so none saw it. Fix:
**v58 = v57 with a 12 ms guard** (installed; 5% of searches cut, same as
with no guard; validate 0.32 ms mean, 4.9 ms slowest; check passed). Rule
added: every candidate is also tested once at the server-equivalent budget
(`lab/evalcount.py`, local budget = server budget / 2.2) before upload.

**The passing gap** (ladder statistics, us vs the median of 8 of the top 20):

| Metric | Us | Top-20 median | Gap |
|---|---|---|---|
| Territory | 55.4% | 55.4% | none |
| Dribbles / match | 89 | 84 | none |
| Passes completed / match | 14.5 | 28.4 | ×2.0 |
| Pass distance / match | 176 | 415 | ×2.4 |
| Shots / match | 4.2 | 5.7 | ×1.4 |
| Goals / match | 2.36 | 4.48 | ×1.9 |
| Goals conceded / match | 0.35 | 0.13 | ×2.7 |

We hold territory and carry the ball as much as the top teams; they move it
by passing, twice as often and further, and score almost twice as much
from a few more shots. This is the clearest single target we have, and it
is measurable locally.

**Bet 6: passing.** Steps:
1. Add passes completed and pass distance (struck kick ≥ 0.5 power,
   collected next by a different team-mate) to `lab/style.py`, and check
   v58's local numbers against its ladder numbers (14.5 / 176).
2. Find why the search prefers carrying: compare the values it gives the
   best pass and the best dribble on captured kick decisions
   (`lab/kickbench.py` capture). Suspects: the keep model's speed term
   (w4 −0.42, w6 −0.74 punishes fast balls, which is every long pass, and
   was fitted only on kicks the search already chose); too few pass
   candidates (one per team-mate at a single speed in the first pass);
   the receiver's onward options not valued (only `la_k` shot lookahead).
3. Variants, each gated on passes completed ↑ **and** goals ↑ vs selfkeep
   (paired), then 540 paired: (a) pass candidates at three speeds and two
   leads per team-mate in the first pass; (b) the keep model's speed terms
   halved for kicks aimed at a team-mate; (c) value a completed pass by the
   best kick the receiver will have (one-step lookahead using the same
   evaluator, top 3 passes only).
4. Ladder upload of the survivor, compared match-by-match with v58 using
   the stored snapshot.

## 18. Bet 6, first results: the keep model was suppressing passes

`lab/style.py` / `lab/paired.py` now report passes completed (struck kick
≥ 0.5 power, next touched by a different team-mate) and pass distance.
Local numbers match the ladder (v57 vs elite 16.7 passes, 195 units per
match; ladder 14.5 / 176). Only 23% of our non-shot struck kicks reach a
team-mate.

Gates (60 paired matches vs selfkeep + elite):

| Variant | Passes | Pass distance | Goals for | Points |
|---|---|---|---|---|
| keep speed terms off (`keep_s4` 0, `keep_s6` 0) | +6.5 ± 1.1 | +93 ± 11 | +0.37 ± 0.16 | +0.12 ± 0.14 |
| margin×speed term off (`keep_s6` 0) | +7.2 ± 1.0 | +64 ± 10 | +0.23 ± 0.17 | +0.08 ± 0.14 |
| margin×speed halved | +3.7 ± 1.1 | +35 ± 10 | +0.20 ± 0.17 | −0.18 ± 0.14 |
| more pass candidates (3 leads × 2 speeds) | −0.8 ± 0.8 | +4 ± 9 | +0.27 ± 0.16 | +0.08 ± 0.13 |

540 paired matches, whole pool, fresh seeds, speed terms off:
passes **+5.1 ± 0.35 (+39%)**, pass distance **+60 ± 4 (+35%)**, goals for
+0.06 ± 0.06, goals against +0.00 ± 0.03, points +0.03 ± 0.06.

Reading:
* The cause of our low passing is the keep model's speed terms (with them,
  margin barely mattered for a fast ball, so every long pass looked risky).
  Removing them moves our style a third of the way to the top teams'
  (21 vs their 28 passes) at no measurable cost — the most robust effect any
  change has had locally.
* More passing alone does not yet produce more goals locally. Top teams
  convert 0.78 goals per shot to our 0.56: passing has to end in better
  shots. That is step 3(c): value a pass by the best kick the receiver will
  have (one-step lookahead with the same evaluator, top 3 passes only).
* Candidate ready: `lab/cand59/` (v59 with speed terms off, 12 ms guard;
  validate 0.26 ms mean, 4.1 ms slowest; 6% of searches cut at the
  server-equivalent budget). Upload order for a clean ladder comparison:
  **v58 first** (the guard fix alone, vs the stored v57 snapshot), then
  **cand59** (vs v58's snapshot).

## 19. Div 4, the guard fix measured, and the receiver lookahead (2026-10-24)

**Div 4 is the field, not us.** The 16:05 ladder run still has v57 (v58 was
not uploaded). Match by match against yesterday's snapshot: 524 matches vs
opponents who did not re-upload are **identical** — *correction:* this is
caching, not determinism (111k matches finish in 90 s, so only a new
upload's matches are played; unchanged pairs are copied). Against 95
re-uploaded opponents we lost 98 points; 44 new entrants +39 net. Replays
are re-simulated on request (`faithful: false`), so they cannot show what
our time guard did on the server. 1976 points, rank 80; Div 3 floor 2003, Div 2 2221.

**The v58 guard fix, measured at server speed** (paired, 120 matches, local
budgets 2.7 ms vs 5.5 ms = server 6 ms vs 12 ms): **+0.31 ± 0.13 points and
+0.53 ± 0.12 goals per match**, +0.93 ± 0.21 points per match vs the bus.
This is the largest measured effect of any change, and it is sitting on
disk. **Upload v58 (`my-team/team.py`) now**; then cand59.

**Receiver lookahead: rejected at the gate** (60 paired vs selfkeep + elite,
base = cand59 config). The old receiver-shot lookahead (`la_k`) turned out
to be dead code at a 32-evaluation cap (it only ran when the search ended
early); freeing it (`la_free`): points −0.08 ± 0.10, goals +0.00 ± 0.09.
General follow-up value (`lb_k` 2 / 3): points −0.05 ± 0.15 / +0.05 ± 0.14,
goals −0.05 / +0.05 ± 0.15; shots +0.3–0.6 but no more goals. Switches stay
in `lab/teams/v60.py`, default off.

**Method change: test on the ladder.** An upload compared with the previous
snapshot gives a paired result (with normal match noise) on every opponent
who has not re-uploaded (about 550 of 948 matches), on the real field. That is better than any local test. From now on: snapshot
after each upload, and judge the next upload on the unchanged opponents.

## 20. Toward Div 2 (2026-10-24): shot quality, and the limit of local tests

**Div 2 comparison** (ladder stats, median of 10 teams ranked 21–40, vs us):
shots 3.81 vs 4.11, goals **3.44 vs 2.24**, goals per shot **0.90 vs 0.55**,
pass distance 255 vs 175, passes 16.5 vs 14.2, dribbles 64 vs 87. They
shoot *less* and score on almost every shot; our gap is shot quality. Part
of our 0.55 is likely v57's blind full-power kicks (they count as shots).

**Shot-quality variants** (base = cand59 settings; paired, 120 matches vs
selfkeep, elite, bus, v48cap):

| Variant | Gate 1 pts / goals | Gate 2 pts / goals | 540 paired | Verdict |
|---|---|---|---|---|
| dominance shot range 30 | +0.09 / +0.07 | −0.03 / +0.04 | — | rejected at gate 2 |
| dominance range 34, goal_bias 1 | +0.06 / +0.16 | +0.14 / +0.09 | **−0.04 ± 0.04** | rejected |
| box man always | +0.11 / +0.15 (±0.10) | — | — | not pursued |
| dribble-to-shoot weight 1.0 | −0.28 / −0.20 | — | — | rejected |

**Conclusion.** Seven tactical changes in a row have measured zero in the
decisive local test, several after passing two gates. The local pool is
saturated: we already take 2.7–2.9 points per match off elite and the bus,
and the rest of the pool is earlier copies of ourselves. Local tests can
still catch *regressions* and *server-condition bugs* (the guard), but they
cannot find the gains that separate us from Div 2.

**Path to Div 2 (≈ +245 points from 1976; floor 2221).**
1. **Upload v58** (`my-team/team.py`). The guard fix measured +0.31 ± 0.13
   points per match at server-equivalent speed; if even two thirds of that
   transfers, that is ≈ +190–290 points, around the Div 2 floor.
2. Snapshot, then **upload cand59** (passing), judged on unchanged opponents.
3. From then on, every tactical idea is tested by upload, one at a time,
   against the previous snapshot; local tests are used only as a safety net
   (no regression vs elite/bus/selfkeep, server-speed check with
   `lab/evalcount.py`).

## 21. v58 on the ladder (2026-10-24 17:05)

0.63 ms mean, 5 timeouts (from 0.72 ms / 41). Paired against the v57
snapshot on 500 matches with unchanged opponents: points +7 (≈ ±29), goals
+0.16 per match, losses 63 → 50, draws 65 → 81. The guard fix helps, but by
about +0.01 points per match, not the +0.31 measured locally. Lesson: the
local "server-equivalent budget" (server time / 2.2) over-states how often
the server truncates the search; the 2.2 factor is a mean over all ticks,
not the kick-tick cost. Don't trust local timing simulations for points.

Current: 2018 points, rank 79, Div 4 (run still in progress); floors D3
2078, D2 2296, D1 2551. Next upload: **cand59** (passing; keep-model speed
terms off), installed as `my-team/team.py`; v58 in `lab/submitted_v58.py`;
v58 snapshot in localStorage `vh_snapshot_v58`.

## 22. cand59 on the ladder, kickoff set play, and a style pool (2026-10-24)

**cand59 (passing) on the ladder**: 2063 points, rank 58, **Div 3** (floor
2040). Paired vs v58 on 928 unchanged-opponent matches: +0.032 ± 0.038
points per match, every rank band slightly positive. Passes completed
14.2 → **20.0 per match** (league rank 32), pass distance 175 → 247: the
passing fix transferred exactly as measured locally.

**Kickoff set play** (`ko_on` in `lab/teams/v61.py`): server-style starts
(engine default spots: everyone wide, nobody near the ball; our taker needs
~55 of the 59 restart ticks to reach it). 600 matches each: scoring within
300 ticks of our kickoff 4.4% → 6.3% (≈ 1.2 SE), nothing conceded. Worth
≈ +0.02 goals per match — parked as a switch.

**A perfect opponent is not feasible**: the engine cannot save/restore a
state (no look-ahead by real rollouts), and a perfect decision maker would
itself be the submission; unlimited search was only modestly stronger.

**Style pool instead** — our engine with different personalities
(`lab/teams/sty_*.py`): passer, shooter, direct, press, counter. Unlike the
hand-written archetypes, they are competitive. cand59 against them (20
matches each): passer 8-10-2, shooter 5-9-6, **direct 3-8-9**, press 8-7-5,
**counter 2-12-6 (50% 0-0)**.

**Rock-paper-scissors.** Playing direct or counter ourselves (paired, 180
matches over the whole pool): −0.08 ± 0.10 / +0.00 ± 0.10 overall, but by
opponent up to ±1 point per match — both lose ~0.9 vs the dribbler
(selfkeep) and gain +0.4 vs the bus; counter gains +0.4 vs the presser.
No style dominates; the right style per opponent is worth a lot. That makes
**opponent-style detection** (10.3) the most promising lever now:

1. Signals already available in-match: their keeper depth, their deepest
   line (bus/deep block), their possession and touch-power share (dribbler),
   their pressing height.
2. Map: deep block / bus → direct settings inside `bus_mode`; dribbler →
   keep cand59; high press → counter settings.
3. Test locally against the whole style pool (paired; the detector must
   beat the best fixed style), then by ladder upload against the v58/c59
   snapshot.

## 23. Opponent-style detection, first version (2026-10-24)

`lab/teams/v62.py` (switch `det_on`): three in-match signals — dribbler
(share of their kicks under 0.3 power), bus (existing deep-defender EMA),
press (EMA of ≥ 2 of their outfielders in our half while we hold the ball
there). `lab/detmodes.py` shows what fires per opponent: dribbler on
selfkeep 91%, bus on the bus 91%; the press signal fires on nearly every
opponent (65–93%), so it does not discriminate.

Paired, 180 matches over the style pool:

| Variant | Overall points | vs bus | Elsewhere |
|---|---|---|---|
| full (bus → direct, press → counter, dribbler guard) | −0.01 ± 0.11 | +0.60 ± 0.26 | press→counter noisy/negative (shooter −0.40, direct −0.70) |
| **bus → direct only** | **+0.07 ± 0.03** | **+0.60 ± 0.26**, GD +1.1 | unchanged (detector does not fire) |

Second independent seed set, bus only, 60 matches: **+0.27 ± 0.13 points,
+0.65 ± 0.25 goals**. Two seed sets agree → accepted.

**Next upload: cand62** = cand59 + detection with only the bus → direct
response (`det_on` 1, `press_on` 2.0), installed as `my-team/team.py`;
validate 0.38 ms mean, 6.0 ms slowest, check passed. cand59 kept in
`lab/submitted_c59.py`. Open question for the ladder: how often our bus
detector fires against real teams (it needs 2.5 of their outfielders deeper
than x = 36; the mid-table 0-0 teams we analysed held a line at x 8–25,
which it will not catch). If it rarely fires, the next step is a "deep
block" signal (their second-deepest outfielder's x) with the same direct
response.

## 24. Deep-block signal: rejected before testing points (2026-10-24)

`lab/blockstat.py`: with the ball ours, the mean x of their second-nearest
outfielder to our goal does separate the pool (bus 42.6; sty_direct 11.4,
midtable 10.4, block 8.2; everyone else 0.2–5.4), and the ladder mid-table
0-0 team looked like sty_direct (line 8.2 / 10.2 / 17.3 / 25.2). But as an
in-match signal (`lab/teams/v63.py`, `blk_on`) it does not: smoothed fast
it fires on elite (52%) more than on sty_direct (32%); smoothed slowly only
11% on sty_direct. Defenders follow the ball, so their instantaneous line
mostly reflects where the ball is. And there is no known response to a
mid-block anyway (direct vs sty_direct −0.30, counter 0.00; base already
beats midtable/block). Stopped under the time-box rule; switch left off.

A better mid-block signal would normalise for the ball (their line relative
to the ball, binned by ball x), but it only pays once a response that
beats a mid-block exists; find the response first, with the ladder as the
judge.

Next upload remains **cand62** (`my-team/team.py`).

## 25. cand62 on the ladder: no gain (2026-10-24 19:24)

Paired vs cand59 on 884 unchanged-opponent matches: −0.017 ± 0.024 points
per match (−15 points), goals for +21, against +23; only 122 results changed.
The bus → direct switch, +0.27 to +0.60 locally against our bus, does not
help on the real field. Recommendation: go back to **cand59**
(`lab/submitted_c59.py`), the best measured build so far (+0.032 vs v58).

Useful side result: only 122 of 884 results changed although every match
was replayed, so ladder results for an identical decision path are nearly
reproducible — paired comparisons on the ladder are low-noise and can
resolve effects of about ±0.025 points per match.

## 26. Final three days (ladder closes 2026-10-27)

Position: rank 58, 2068 points, exactly on the Div 3 floor; the field drifts
up by tens of points a day as others re-upload, so standing still means
Div 4. `my-team/team.py` is back to **cand59** (best measured build;
cand62 kept as `lab/submitted_c62.py`). **Re-upload cand59 now.**

Rules for the last three days:
* Only changes that can be measured *before* upload, and only uploads that
  are judged against the previous snapshot (±0.025 points per match).
* Any upload that measures negative is reverted at once to the last good
  build.
* No uploads after the evening of 26 Oct except a revert; 27 Oct is for
  making sure the final build is the best measured one, `team.toml` is
  filled in, and `validate` + `check` pass.

Schedule:
* **24–25 Oct — keeper bet.** Build a "sniper" sparring team in the real
  engine that reproduces how the top 40 score on us (carry to 19–32 units,
  strike at 18–25 u/s into the corner away from our keeper). Measure our
  goals conceded per shot against it; improve the keeper (positioning
  against those shots, earlier commitment, near/far-post choice) until it
  concedes clearly fewer; check no regression against the pool; upload.
* **25–26 Oct — shot selection**, only if the keeper lands: shoot only when
  the exact reach of their keeper and defenders says the shot cannot be
  stopped; measure goals per shot against the pool; upload if positive.
* **26 Oct evening:** last tactical upload. **27 Oct:** keep or revert.

## 27. Keeper bet (2026-10-24 evening)

**How top teams score on us** (16 goals conceded to top-30 teams, 8 of our
own ladder matches, browser-side): 13 of 16 struck from 10–20 units at
~23 u/s, 14 of 16 after the scorer dribbled 2–3 touches, nearest defender
3–10 units away, our keeper 7+ units out in 4, 9 of 16 from wide, 2 own
goals.

**Local pool cannot see it**: keeper settings moved goals against by
±0.03 in full matches; a "sniper" (dribble + shoot inside 21) loses 16-3-1
with 0.8 shots per match — nobody local gets to that zone.

**Shooting gallery** (`lab/gallery.py`, real engine): our outfielders step
aside; a scripted attacker dribbles to random spots 14–20 units out and
strikes at the far post at full power. Strikes conceded (≈ 420 per row,
±2%):

| Keeper (assumed shot speed / max metres off line) | Conceded |
|---|---|
| current 28 / 12 | 33.1% (fresh seeds 29.1%) |
| stay home: max 6 / 4 / 2.5 | 43% / 49% / 48% |
| 32 / 12 · 36 / 12 · 40 / 12 · 48 / 12 | 26.8 · 24.1 · 21.4 · 18.8% |
| **36 / 16** | **15.4% (fresh seeds 15.0%)** |
| 48 / 16 · 40 / 20 · 36 / 20 | 11.0 · 11.4 · 10.9% |

Full matches over the style pool (paired, 180): 36/16 +0.04 ± 0.09 points,
goals against −0.02 ± 0.05; 40/20 +0.05 ± 0.08 — no regression.

**cand64** = cand59 + keeper 36/16, installed as `my-team/team.py`
(validate 0.25 ms mean, 3.2 ms slowest; check passed; gallery 18.5% on a
third seed set). Chose the moderate setting over 40/20 because 9 of 16
ladder goals came from wide, where a far-out keeper is most exposed to a
ball across the box. If cand64 measures positive on the ladder, 40/20 is the
next upload; if negative, revert to cand59 (`lab/submitted_c59.py`).

## 28. cand64 on the ladder: worse — reverted (2026-10-24 21:09)

Paired vs cand59 (796 matches): −0.024 ± 0.034 points per match, but goals
against **+40** (290 → 330), mostly vs the top 40 (ranks 21–40 points 25 →
13). vs cand62 the same (against +18, ranks 21–40 points 30 → 14). The
shooting gallery measured the wrong thing: real top teams pass across the
box and go round a keeper who has come out; a gallery that only shoots
rewards an aggressive keeper. Lesson: a local test that isolates one
mechanism can mislead in the direction of over-fitting to it. Reverted to
cand59 (`my-team/team.py`); cand64 kept as `lab/submitted_c64.py`.

Position: 2076 points, 3 below the Div 3 floor (2079), run in progress.

## 29. Night of 24 Oct: speed is the safe lever; kickoff play dropped

* Decision time inside a division (current run): Div 3 means 0.06–1.06 ms,
  Div 4 0.04–0.66. At our 0.65 ms we are 19th of 20 in either; 0.4 ms →
  12th–14th, 0.3 ms → 8th–12th, 0.2 ms → 4th–7th.
* Keeper position is bimodal (≈ 1.5 or 10–15 units out); cand64's settings
  made it rush out against shooters up to 25 units away — what the top
  teams punished. Keeper tuning parked.
* Kickoff set play in paired full matches (180): −0.03 ± 0.08 points, goal
  difference −0.12 ± 0.07 → dropped despite the kickoff-window gain.
* **cand65** = cand59 decisions exactly (lockstep 0 diffs, two seeds) with
  the keeper-spot table filled when the team is created (125 ms at load)
  instead of during matches: 0.300 → 0.285 ms locally. Installed as
  `my-team/team.py`; uploading it also restores cand59's play.

## 30. plan2 item W, wall when leading (2026-10-25)

`lab/teams/v66.py` (switches `wall_on`, `wall_min_lead`, `wall_late`,
`wall_kick`): four on our goal line at y = c + (±1.9, ±5.7), keeper 4 off
the line, nobody chases, full-power clearance into the first open lane.
Paired vs cand65 over the style pool:

| Trigger | Points/match | Against | Verdict |
|---|---|---|---|
| any lead (plan2 W) | −0.12 ± 0.05 | +0.11 | rejected |
| any lead, search kick (8 evals) | −0.33 ± 0.06 | +0.24 | rejected |
| 1-goal lead in 2nd half, 2+ always | +0.04 ± 0.04, then **−0.10 ± 0.04** | +0.07 | rejected on 2nd seed set |
| **2+ goals up only** | **±0.00** (not one result changed in 450 matches) | +0.02 / +0.04 | **accepted for speed** |

Our wall leaks against a team pressing for an equaliser; it is not Team-034's.
But from two up the result is safe, and walled ticks are nearly free:
mean decision time against beatable teams (elite, bus, balanced; own
matches) 0.321 → **0.158 ms**. Goal difference falls (fewer goals scored
from 2 up) — it only matters for exact ties on points.

**cand66** = cand65 + wall from 2 up, installed as `my-team/team.py`
(validate 0.24 ms mean, 4.5 ms slowest; check passed).

## 31. plan2 item R1, counter window: rejected (2026-10-25)

`lab/teams/v67.py` (`cw_on`): after we win the ball with their outfield
averaging > 45 (or 38) from their goal, for 150 ticks: shot_range 30,
goal_bias 1, xt_scale 3.5, lose_pen 0.04, max_evals 16. Paired on top of
cand66, 180 matches over the style pool:

| Variant | Points/match | Against |
|---|---|---|
| as specified | −0.24 ± 0.09 | +0.08 |
| without the evaluation cut | −0.13 ± 0.09 | +0.06 |
| window from depth 38 | −0.24 ± 0.10 | +0.07 |

Playing "forward, now" loses the ball more and concedes more; no variant
helps any opponent consistently. Dropped under the time-box rule.

## 32. plan2 §13 speed package (2026-10-25)

cand66 on the ladder (09:24): 0.50 ms (from 0.61), 2 timeouts; paired vs the
cand59 snapshot (616 matches) −0.026 ± 0.030 points, goals against +51
(the 2-0 wall leaks against real teams; points within noise; plan2's own
pairing vs cand65 over 876 matches: +0.000).

`lab/teams/v68.py` switches, paired vs cand66 (270 matches, style pool):

| Switch | Points/match | Time | Verdict |
|---|---|---|---|
| S1+S2+S3 stack | **−0.56 ± 0.08** | −26% | rejected |
| S3: max_evals 16 in our own half | **−0.51 ± 0.07** | −4% | rejected — own-half kicks matter most |
| S1b: max_evals 24 | −0.16 ± 0.08 | ≈ −8% | rejected |
| (S1 reuse_k 5: −0.43 vs selfkeep, §16) | | | rejected earlier |
| **S2: pc_every 12** | **+0.06 ± 0.09** | **−8%** | accepted |
| **R3a all-in late + S4 decided path** | **0.00 ± 0.01** | small | accepted |
| S2 + R3a + S4, fresh seeds | 0.00 ± 0.09 | −7–9% | **→ cand68** |

**cand68** installed as `my-team/team.py` (cand66 in `lab/submitted_c66.py`).

## Sources consulted

* HELIOS / agent2d chain-action search (Akiyama et al., 2012) — our anytime
  kick search is the same shape; depth-2 pass→shot is what `la_k` does:
  [TDP HELIOS2013](https://staff.fnwi.uva.nl/a.visser/activities/robocup/RoboCup2013/Symposium/TeamDescriptionPapers/SoccerSimulation/Soccer2D/TDP_HELIOS2013.pdf),
  [helios-base](https://github.com/helios-base/helios-base),
  [HELIOS2023](https://tdp.robocup.org/wp-content/uploads/tdp/robocup/2023/robocupsoccer-simulation-2d/helios2023-423/robocup-2023-robocupsoccer-simulation-2d-helios2023IcpkzBKvS6.pdf).
* Learned single-pass candidate generation replacing repeated evaluator calls
  (basis for A3): [SPO: Single Pass Optimization for Soccer Simulation 2D](https://sol.sbc.org.br/index.php/sbrlars/article/view/33929);
  pass prediction features: [arXiv 2401.03410](https://arxiv.org/pdf/2401.03410).
* Keeper placement on the ball–goal line and the far-post weakness (C3/D2):
  [Human-Like Goalkeeping (arXiv 2510.23216)](https://arxiv.org/html/2510.23216v3);
  shot evaluation with a goalie-movement model:
  [FC Portugal shooting approach](https://web.fe.up.pt/~lpreis/Papers/FCPortugalShootingApproach.PDF);
  learned shot-point selection: [LegenDary 2013 TDP](https://staff.fnwi.uva.nl/a.visser/activities/robocup/RoboCup2013/Symposium/TeamDescriptionPapers/SoccerSimulation/Soccer2D/TDP_LegenDary2013.pdf).
* Ladder data: https://lamp.ms.wits.ac.za/soccer/#/standings (`api/table`,
  `api/team?slug=<student-no>-victor-hyginus`, `api/replay?name=ladder/<id>`).
