# plan2 — Moving Victor_Hyginus up the ladder (with low decision time)

Written 2026-10-25, about 2 days before the ladder closes (plan.md §26 gives the close as 2026-10-27).
This plan comes from three sources:
- the live ladder API (`api/table`, `api/team`, `api/matches`, `api/replay`, `api/doc`);
- about 40 downloaded replays;
- the experiment history in plan.md.

It replaces nothing in plan.md. plan.md is still the record of what was tried; this file is the next attack.

---

## 0. TL;DR

1. **We are not losing on attack quality. We lose because we never win 1-0 and we never protect leads.**
   - Against the top 60 we go 29-43-168 (W-D-L), and almost every loss is 0-1 or 0-2.
   - The best "small" teams (Team-196, rank 4; Team-034, rank 8) score once, then park all 5 players on their own goal line. Team-196 wins 1-0 in 83% of matches and Team-034 in 89%.
   - We lose leads in roughly 30-35 matches, worth about **50-80 points**.
2. **The fix is cheap: a "wall when leading" mode.** It needs almost no computation, so it also **cuts our mean decision time** a lot. We lead in a large share of ticks, and in those ticks we would skip the kick search.
3. Then come two weaker, ladder-test-only items:
   - **a shot-lane screen** (our "shots blocked" is 1.09 per match, rank 201/254; Team-034 blocks 6.5);
   - **rest defence against counter teams**, so we stop conceding the first goal while our defenders are 20-35 units up the pitch.
4. Stretch item: **an anti-wall attack** copied from the teams that beat goal-line walls (Team-022 beat Team-121 6-0). It works by carrying the ball centrally with tiny touches and shooting at full power from 12-15 units.
   - **Superseded by §11 (research round 2).** Most of our 0-0s are *not* against walls. They are against mid-table teams that Team-034, Team-196 and Team-248 all beat. In those games we reach the final third about 4 times and take 0-2 shots, so the bigger lever is a **counter-window attack plus shot volume** (§11, R1).
5. Realistic target: **Division 3** (≈ +100 points, i.e. +0.10 points per match). Division 2 (+370) is not realistic in 2 days. Inside whichever division we land in, a lower decision time moves us up, because rank inside a division is ordered by mean decision time.

---

## 1. Where we stand (ladder run started 2026-10-25 04:01, 254 teams)

### Our numbers

| | Value |
|---|---|
| Rank | **77** (Division 4) |
| Points | 2072-2084 (still updating) |
| W-D-L | 633-173-202 (≈1008 matches) |
| Goals | GF 2.13 / GA 0.41 per match |
| Decision time | **0.603 ms** mean, 22 timeouts (none near the 20-in-a-row forfeit) |

### Division floors and the points we would need

| Division | Floor | Gap |
|---|---|---|
| D1 | 2682 | +610 |
| D2 | 2441 | +370 |
| D3 | 2171 | **+~100** |
| D4 | 1883 | (we are here) |

### Decision time

- Division 4 times range from 0.06 to 0.94 ms. We are about 17th fastest of 20, so **we are near the bottom of our own division on time**.
- The leaders run at 0.05-0.20 ms. The #1 team, Team-053, runs at 0.10 ms and scores 4.19 goals per match.
- So low time and strong play are not in conflict. Their speed comes from simple, decisive rules, not from searching.

### Our stats (rank out of 254)

| Stat | Value | Rank | Comment |
|---|---|---|---|
| Passes | 19.8 | 37 | fine |
| Dribbles | 77 | 52 | fine |
| Territory | 51.9% | 73 | fine |
| Shots | 3.86 | 149 | low |
| Interceptions | 10.2 | 127 | |
| **Shots blocked** | **1.09** | **201** | worst area: shots on us go unscreened |
| Fouls | 0 | | |

### How the server ranks teams (student guide §8 and §10)

- Teams are cut into divisions of 20 by points, then ordered by mean decision time inside each division.
- Final grading uses a **hidden seed set**, not the ladder seeds 1000-1003. **Do not tune to ladder seeds.** Every idea below is behaviour-level, not seed-level.

---

## 2. Where the points go (952 points lost)

### By opponent rank

| Opponent rank | W-D-L | Points lost | What happens |
|---|---|---|---|
| 1-20 | 1-12-67 | 225 | We score 0.19 per match. Lost 0-1 / 0-2. |
| 21-40 | 8-15-57 | 201 | Same pattern. |
| 41-60 | 20-16-44 | 164 | Many of these are counter/wall teams. |
| 61-100 | 63-66-27 | 213 | 49 0-0 draws. |
| 101-150 | 143-50-7 | 121 | 44 0-0 draws against weaker teams. |
| 151+ | 398-14-0 | 28 | Already maxed. |

### Most common score lines

| Score | Matches |
|---|---|
| 0-0 | 131 |
| 0-1 | 105 |
| 0-2 | 45 |

That is 281 matches (28%) where we scored nothing. Points are lost through **scoreless draws and narrow defeats**, not blowouts.

### Points lost by opponent territory

| Opponent territory | Points lost | Meaning |
|---|---|---|
| 45-55 | 419 | even teams |
| ≥55 | 310 | possession teams |
| <35 | 119 | wall/counter teams |
| 35-45 | 104 | |

### Against counter/wall teams in the top 60

- Our record is **9-3-40**.
- The teams are Team-034, Team-196, Team-106, Team-199, Team-225, Team-091, Team-173, Team-168, Team-007, Team-244, Team-226, Team-071 and Team-072.
- In every replay against them, **they scored first** and we then could not score past the wall.

---

## 3. Key discovery: "score once, then wall"

### Evidence

- **Team-196** (rank 4, 0.17 ms) and **Team-034** (rank 8, 0.37 ms):
  - 1-0 wins in **83% / 89%** of all their matches;
  - GF ≈ 0.97, GA ≈ 0.15-0.17, territory 26%, **6.5-6.7 shots blocked per match**.
- Team-034 beats top-10 attacking teams 1-0 once ahead: Team-053 3× 1-0, Team-073 4× 1-0.
- When Team-034 falls behind, they lose 1-2 or 1-3. **The wall is only a lead-protection device.** It does not win from behind.

### Wall geometry

Taken from replay `m-5bcafc8d0b1b2da0`, ticks 1100-2300, using `lab/_wallpos.py`.

- **Keeper** about 4 units off the line (x ≈ −46), sliding with the ball's y on the ball–goal line.
- **4 outfielders** on the goal line at x ≈ −47.5 to −49, spaced about 3.5-4.0 apart in y. The whole wall shifts toward the ball side.
  - Example: with the ball at y = 17, the outfielders stood at y = −3.5, 0.4, 4.4 and 8.3. That is a centre of about +2.4 ≈ 0.14 × ball_y, with spacing about 3.9.
- **No pressing.** They wait until the ball arrives, then clear it hard (power ≈ 1.0) up the pitch or to a wing.
- The goal is 14 wide and players have radius 1. Four bodies plus the keeper leave almost no straight-line path to goal. Attackers can only shoot through bodies, which explains the 6.5 blocks per match.

### How the walls scored their first goal on us

From `lab/_gtl.txt`: Team-034 scored at ticks 974, 467 and 481; Team-196 at 1688.

- Each goal came from a wide dribble or switch pass (power ≈ 1.0) to a man 10-20 units out, a few small touches, then a full-power shot.
- **Our outfield depth at the moment we conceded was 20-34**: our "defenders" were high and the far side was open.
- After going behind, our whole team pushed up (outfield depth 64-85) and we never scored.

### Why this matters for us

We lead in a large share of our matches. In a sample of 7 informative "scored but didn't win" replays (`lab/_gtl2.txt`), **4 were leads we let slip**:

| Opponent | Result | Replay |
|---|---|---|
| Team-226 | 1-0 up, lost 1-2 | `m-ba6db4bb55053f28` |
| Team-119 | 1-0, drew 1-1 | `m-62bb4ef4d8512389` (equaliser at t2037) |
| Team-d91 | drew 1-1 | `m-e65687d23034a140` |
| Team-007 | 1-0 up at t290, drew 1-1 | `m-44ff71149f2113ae` |

- Scaled to the 68 "scored but didn't win" matches, that is roughly 30-35 lost leads, worth **+50-80 points** if a wall holds them.
- We already have a late version of this: `gs_protect`, which only applies when `time_remaining < 0.5` and only changes kick valuation. It does not change positioning.

---

## 4. How opponents score on us

From `lab/_gtl.txt`, `lab/_gtl2.txt` and plan.md §27, where 9 of 16 goals came from wide.

1. **Small-touch dribbles** (power 0.03-0.2) straight at goal through the middle, then a 1.0-power shot from 15-20 units.
   - Team-144 scored at t364 and t649 this way. Each time **no defender was standing on the ball–goal line**.
2. **Crosses or switches finished first time** at the far post or the cut-back spot.
   - Examples: Team-d91 t765, Team-d3b t1400, Team-223 t1640, Team-119 t2037.
3. Concessions happen with our outfield depth 15-35, meaning **our back line is not between the ball and the goal**.

### What our defence does today (`defence_plan`, team.py ~L1385)

- one cover man on the ball–goal line at `cover_dist`;
- a cut-back guard (`box_guard`) only when the ball is wide (`hx < wide_x and |hy| > wide_y`);
- goalside man-marking of the others;
- a spare at (−36, 0).

### What is missing

- A **body on the shot line** when a dribbler is 12-30 units out in a central position. The cover man is at `cover_dist` *from the ball*, so a carrier simply goes around him.
- A **far-side cover** against switches.
- A **rest defence** while we attack. When we lose the ball we have nobody deep except the keeper.

---

## 5. How teams beat goal-line walls

This matters for our 0-0 draws.

- **Team-121** (territory 16.8%, 554 0-0 draws) walls the whole game and draws 0-0 with many top teams.
- These teams beat it heavily:
  - Team-022: 6, 4, 5, 4 goals
  - Team-179: 3, 4, 4, 3
  - Team-138: up to 6
  - Team-085 and Team-073

### Team-022's pattern

Replay `m-368f320d3201a42b`, `lab/_gtl3.txt`.

- One player (id 9) **carries centrally with tiny touches** (power 0.03-0.19) from x ≈ −7 to x ≈ −36, centre-right (y 3-17).
- He then **shoots at power 1.0 from 12-15 units** (x ≈ −35 to −39, y ≈ 2.6-4.9).
- Two goals came from **scrambles and rebounds in the box** after a cross (t1142, t1815). Many bodies near goal produce deflections.

### Team-138's pattern

Replay `m-7ba45c21212e6606`.

- Passes across the box at x ≈ −43, and crosses at power 0.55-0.95 finished first time.
- One goal was a **keeper own goal**. Walls are vulnerable to balls driven across the face of goal.

### Caveat

Team-121's wall sits further out (depth ≈ 13-15), not on the line like Team-034's. A carry-and-shoot from 12-15 units works because the shooter gets **inside** the wall's x. Against a true goal-line wall, the cross or cut-back across the face of goal is the better weapon.

### Our current anti-wall mode

`bus_mode` (triggered by `self.deep >= bus_n`) only sets `goal_bias = 0`. It does not change *how* we attack.

---

## 6. The plan, in priority order

Each item has:
- what to build;
- where it goes in `my-team/team.py`;
- its decision-time effect;
- a ladder gate (paired against the cand65 snapshot, as in plan.md §12).

The test rule stays: **one change per upload, keep the last good version as a fallback.**

### W — Wall when leading (highest value, lowest cost) ★ upload 1

#### Trigger

- `sg > so` (any lead).
- Team-034 and Team-196 wall from the first goal and it works even against the top-10 attackers.
- Exit as soon as the lead is gone (that is a natural hysteresis).
- **Wall straight away on the opponent's kickoff after we score.** The wall slots are far from the centre circle, so the kickoff restriction is satisfied automatically. Still call `keep_out` on that tick.
- Fallback variant W' if W gates badly: trigger only when `time_remaining < 0.6`, or when `lead >= 1 and terr < dom_on` (we are not dominating).

#### Implementation

Add a new early branch in `decide()`, right after the score is read (~L814) and **before** `reuse_plan`, `ball_path` and the `first_intercept` scans. That is what makes it nearly free to compute.

- `self.plan_cache = None` so plan reuse cannot replay a pre-wall plan.
- **Keeper:**
  - stand at x = −XL + 4 (= −46), y = clamp(by × 0.25, −5, 5);
  - keep `keeper_move` for real shots: if `gside == -1` (ball heading into our goal), use the existing keeper logic. That costs one `ball_path` call only when the ball is moving toward us.
- **Four outfielders:**
  - slots at x = −48.5 and y = c + {−5.7, −1.9, +1.9, +5.7}, with c = clamp(0.14 × by, −3, 3);
  - assign by sorting players by y and matching them to slots by y. That is O(4), so no Hungarian or nearest search is needed.
- **Kicker:** if any of our players can kick (`obs.can_kick` / the existing kicker loop), clear the ball.
  - Take 3 fixed targets, (+30, +27), (+30, −27) and (+45, 0). Pick the first one whose straight lane has no opponent within 2.5 units, by a point-to-segment check against 5 opponents.
  - Kick at full power toward the wing on the ball's side first.
  - This is a deliberate, cheap replacement for `choose_kick` (~0.02 ms instead of a 32-eval search).
  - Optional variant W-b: keep `choose_kick` but with `max_evals = 8` and `goal_units` low. Keeping the ball also wastes time, but costs more.
- **Never chase.** A goal-line wall that sends one man out leaves a hole; Team-034 does not press.

#### Decision-time effect

- Walled ticks cost about 0.02-0.05 ms, versus about 0.6 ms now.
- We lead for a large fraction of ticks against the 151+ band (398-14-0) and much of the 101-150 band, so mean time should fall about 30-45% (≈ 0.60 → ≈ 0.35-0.40 ms server time).
- That moves us several places up inside whichever division we are in.

#### Risks

- **We stop scoring after 1-0.** Points do not care about goal difference, and the table orders by points then decision time.
- **A siege for 2000 ticks against strong attackers.** But we lose those ties anyway, and Team-034's record shows the line holds against them.
- **Own goals from deflections**, as Team-121's keeper did. Keep the keeper *in front of* the wall (x −46 vs −48.5) so the ball meets the keeper first.

#### Gates

1. **Locally:** run `python -m soccer validate` / `check`.
2. **Timing:** run `lab/timing.py` against an elite opponent. Mean time should drop and p99 must stay under 12 ms.
3. **Sanity:** use `lab/paired.py` against `selfkeep.py` and `bus.py`, 30 seeds (for example `--seeds 7700..7729`).
   - Must not lose points against `selfkeep`.
   - Expect the win rate when 1-0 up to rise.
   - The local pool is saturated, so this is a sanity check, not proof.
4. **Ladder:** ≥ +0.03 points per match paired against cand65 (≈ +30 points), and decision time lower. If worse, re-upload cand65 and try W'.

### D — Defensive shot screen and rest defence ★ upload 2 (only if W passed; stack on W)

#### D1. Shot-lane screen

In `defence_plan` (~L1385), when the threat point `(hx, hy)` has hx < −15 and |hy| < 15, add a first target:
- the point on the ball–goal-centre segment, 3.5 units from the ball, toward goal;
- this target replaces the current `cover_dist` cover when the carrier is central and close.
- It counters the Team-144-type central dribble and should raise shots blocked.

#### D2. Far-side cover

When `hx < −25` and `|hy| > 6`:
- put one target at (−42, −sign(hy) × 6), the far post / cut-back lane;
- this extends `box_guard`, which today only fires when `|hy| > wide_y = 9` and only on the near side's mirror;
- it counters switches finished first time (Team-d91, Team-d3b, Team-223, Team-119).

#### D3. Rest defence

In `support_plan` while attacking:
- hold back the furthest-back non-chaser at x ≤ max(hx − 30, −30), central;
- hold back two when `self.deep >= bus_n` (the opponent is a counter/wall team: deep players).
- This answers "we conceded the first goal with outfield depth 20-34".
- Against wall teams the first goal decides the match. A 0-0 against them is +1 point per match, versus the 0-1 we get now in 40 of 52 matches.

#### Cost and gate

- Cost: a few arithmetic operations, so no time impact.
- **plan.md history warning:** previous hand-written defensive tweaks (cand64's aggressive keeper, the second presser, carrier chase) measured zero or negative on the ladder. That is why this is one upload, gated hard.
- Gate: ≥ +0.02 points per match versus W alone, otherwise revert to W.

### A — Anti-wall attack (stretch, upload 3)

Improve `bus_mode` (only active when the opponent keeps ≥ 2.5 players past x = 36, so it cannot hurt normal matches).

1. **Carry central, then shoot.** In bus mode:
   - raise the value of short central carries toward (+35, ±4);
   - set `shot_range` to about 16 (shoot only when inside 12-16 units);
   - use full-power shots aimed at the far post across the wall line.
   - This is Team-022's pattern.
2. **Cut-backs and crosses across the face of goal.** Give a bonus to passes whose target is x ∈ [38, 45], |y| < 6, with a teammate arriving. Driven balls across the goal mouth create deflections and own goals (Team-138 vs Team-121).
3. Bus ticks are only a few percent of the total, so there is no measurable time impact.
4. Gate: ≥ +0.02 points per match. The effect shows up in the 61-150 bands' 0-0 draws: 93 of them, where converting 20% into wins would be worth about +37 points.

### T — Further decision-time cuts (no points risk)

- **T1. Blow-out mode:** when `sg − so >= 2` and W is not active (only if W' is used), use `max_evals = 8` and `reuse_k = 5`.
  - plan.md recorded that reuse_k 5 / max_evals 24 gave no points change.
  - When we are 2 up, the result almost never changes, so this is time saved for free.
- **T2. Opponent kickoff after our goal:** the wall already applies (we are leading). Make sure `keep_out` still runs so we do not foul the restart rule (`outside_circle`).
- **T3.** Do **not** cut the budget guard below 12 ms. The 6 ms guard regressed play (plan.md, v54/v57).

---

## 7. Upload schedule (≈ 2 days, 3-4 uploads)

| When | Upload | Contents | Fallback |
|---|---|---|---|
| Oct 25 evening | U1 | cand65 + **W** (wall when leading, cheap clearances) | cand65 |
| Oct 26 midday | U2 | If U1 passed: U1 + **D** (screen, far-side cover, rest defence). If U1 failed: cand65 + **W'** (late/non-dominant trigger). | U1 or cand65 |
| Oct 26 night | U3 | Best so far + **R1** (counter window + shot volume, §11). Use **A** only if R1 is not ready. | best so far |
| Oct 27 (before close) | Final | Re-upload the **best measured** version, so the final table runs on it | — |

### Checklist for every upload

- [ ] Change is isolated and documented in `lab/ladder_log.md` (name, diff, expectation).
- [ ] `python -m soccer validate my-team` and `check` pass. `team.toml` name and student number are correct.
- [ ] `lab/timing.py`: mean down or equal, p99 < 12 ms, no first-tick spike. Init builds the keeper table at construction, which is allowed.
- [ ] `lab/paired.py` sanity run against `selfkeep`, `bus` and `sty_counter`, 30 seeds: no blow-ups.
- [ ] Snapshot the current ladder row (localStorage `vh_snapshot_*`) **before** uploading, so the paired comparison is against unchanged opponents.
- [ ] After the run, compare per-opponent results (`lab/_lost.py`, `lab/_buckets.py`), especially:
  - the 41-150 rank bands (where W and D should bite);
  - the counter teams (9-3-40 today).

---

## 8. Expected outcome

| Item | Mechanism | Estimate |
|---|---|---|
| W | hold about half of ~30-35 lost leads | +50-80 points |
| D | fewer first goals conceded to counter/wall teams; fewer central-dribble goals | +0-40 points (uncertain; history says defence tweaks are hard) |
| A | convert some of 93 0-0 draws against the 61-150 bands | +0-37 points |
| T + W | mean decision time 0.60 → ~0.35 ms | several places within the division |

- **Total:** about +50 to +150 points. That is roughly 2120-2230, which puts **Division 3 (floor ≈ 2171) in reach**.
- With a lower decision time, we would also sit higher *inside* the division than today's 17th of 20.
- The floors move as other teams upload too, so treat D3 as the goal and D2 as out of reach before close.

---

## 9. What not to do (from plan.md and this research)

- Do not tune to seeds 1000-1003. Grading is on hidden seeds.
- Do not re-try what already measured zero or negative:
  - aggressive keeper (cand64);
  - bus→direct detection (cand62);
  - kickoff set play;
  - carrier chase;
  - second presser;
  - keep-model refit;
  - a 6 ms guard.
- Do not trust replay scores blindly. Replays are re-simulated and sometimes differ from ladder results. Use them for *patterns*, and use `api/matches` for *results*.
- `initial_formation` appears to be ignored by the server (both teams start at engine defaults plus jitter). Do not spend time on it.
- Do not stack several untested changes in one upload. With about 3 uploads left, an unexplained regression costs the rest of the window.

---

## 10. Evidence index (lab/, temporary `_` files)

### Scripts

| File | Purpose |
|---|---|
| `_ladder_summary.py` | table summary |
| `_buckets.py` | record by opponent rank band and style |
| `_lost.py` | points lost per opponent |
| `_ties.py` | a team's results against the top N |
| `_teamscores.py` | score distribution and stats for any team |
| `_goaltl.py` | downloads replays; goal timelines, depth, build-up kicks |
| `_wallpos.py` | player positions at chosen ticks |
| `_leadsample.py` | samples our "scored but didn't win" matches |

### Outputs

| File | Contents |
|---|---|
| `_gtl.txt` | Team-034 and Team-196 against us and against top teams |
| `_gtl2.txt` | our lost leads |
| `_gtl3.txt` | Team-121 vs Team-022 6-0, Team-121 vs Team-138 |

### Key replays

| Replay | What it shows |
|---|---|
| `m-5bcafc8d0b1b2da0` | Team-034's wall geometry |
| `m-368f320d3201a42b` | Team-022 breaks Team-121 |
| `m-7ba45c21212e6606` | Team-138 breaks Team-121 |
| `m-ba6db4bb55053f28` | Team-226 turns 0-1 into 2-1, then walls |
| `m-62bb4ef4d8512389`, `m-44ff71149f2113ae`, `m-e65687d23034a140` | our lost leads |

### Cleanup

The `lab/_rep_*.json` replay downloads are about 8 MB each and can be deleted once this plan is executed.

---

## 11. Research round 2 — more strategies and algorithms

This round has two sources:
1. **More ladder evidence:**
   - which opponents we draw 0-0 with (`lab/_zz.py`);
   - band-by-band comparison with the top teams (`lab/_bandcmp.py`);
   - per-match shot and final-third analysis (`lab/_shotan.py` → `_shot1.txt`, `_shot2.txt`);
   - empirical shot outcomes (`lab/_xgemp.py` → `_xgemp.txt`).
2. **Published robot-soccer and sports-analytics methods**, each checked for cost per tick.

### 11.1 New evidence: the 0-0 problem is an attack problem against mid-table teams

#### Points per match by opponent band (`lab/_bandcmp.py`)

| Opponent rank | Us | Team-034 (#8) | Team-196 (#4) | Team-248 (#7) | Team-053 (#1) |
|---|---|---|---|---|---|
| 1-20 | 0.19 | 1.42 | 1.32 | 1.87 | 1.14 |
| 21-40 | 0.49 | 1.98 | 1.90 | 2.48 | 1.90 |
| 41-60 | 0.95 | 2.69 | 2.65 | 2.77 | 2.59 |
| 61-100 | 1.63 | 2.86 | 2.74 | 2.94 | 2.80 |
| 101-150 | 2.40 | 2.99 | 2.93 | 2.91 | 2.95 |

#### The 0-0 opponents are beatable

- **104 of our matches against 62 teams ranked 41-150 end 0-0.**
- Against exactly those teams, the top teams' records are:
  - Team-034 **237-8-3**
  - Team-196 **223-23-2**
  - Team-248 **231-15-2**
- So these teams are not unbeatable; we just do not score against them. Each 0-0 turned into a 1-0 is +2 points, so the ceiling is about **+200 points**. That is more than every lever in §6 combined.

#### Our attack against them

Replays against Team-008 (#69, four 0-0s with us) and Team-009 (#71):

| Match | Our possession | Final-third entries | Shots |
|---|---|---|---|
| vs Team-008 | 46% | 4 | **0** |
| vs Team-009 | 53% | 4 | **2** |

- These opponents are **not** walls. Their outfield sits 26-37 units from their goal while we attack. They press and hold the ball themselves.
- So the anti-wall item A in §6 targets the wrong opponents for these points.

#### How the top teams beat the same opponents

- **Team-034 (18% possession!)** gets 7 final-third entries through direct play:
  - long full-power switches from the wing (y ≈ 27) into the centre;
  - one or two touches;
  - a shot or square ball from about 10 units.
- **Team-248** scored 3 of 5 against Team-008 with **power-1.0 shots from 20-28 units**:
  - each came about 100-150 ticks (5-7 s) after winning the ball, via 2-3 long passes;
  - Team-008's outfield was still **55-72 units** from its own goal (caught upfield);
  - the build-up was a long ball to a wing (y ≈ 27), then forward.
- This is a **transition (counter-attack) goal**. The window is the 5-7 seconds after a turnover, while the opponent's shape is still broken.

#### Empirical shot outcomes (28 ladder replays, on-target shots with power ≥ 0.75)

| Distance | Clear lane | 1 body in lane | 2+ bodies |
|---|---|---|---|
| < 10 | 0.53 (15) | 0.09 (32) | 0.04 (49) |
| 10-15 | **0.80** (10) | 0.33 (18) | 0.00 (19) |
| 15-20 | 0.12 (8) | 0.10 (10) | 0.00 (5) |
| 20-28 | 0.00 (6) | 0.08 (13) | 0.00 (4) |

- The sample is small and skewed toward wall matches, so treat it as **direction, not calibration**.
- Even so, the signal is strong:
  - a **clear lane from 10-15 units is close to a goal**;
  - shooting through two bodies almost never works;
  - long shots only pay when the defence is caught upfield (Team-248's case).

### 11.2 Strategies and algorithms, ranked by value per day of work and per microsecond

#### R1 — Counter-window attack plus shot volume ★ best new lever (fits upload 3)

*Basis:* transition-attack analysis (the Team-248 and Team-034 evidence above), and the football-analytics finding that fast breaks after regains produce a large share of goals against organised teams.

**Detection (O(5) per tick):**
- `opp_depth` = mean of `XL - o.x` over their four outfielders (we already loop over opponents for `self.deep`).
- `regain_tick` = the tick our side gained possession. Track it from changes in our `attacking` flag, or from `update_restart`.
- **Counter window** = `tick - regain_tick < 150` and `opp_depth > 45` (their outfield is caught high).

**Behaviour in the window**, using a parameter overlay through the existing `mode_cache` mechanism (same as `dom_mode` and `bus_mode`):
- `shot_range` 32 → about 30, and shoot when the lane is clear even at 20-28 units;
- a **forward-pass bonus** (an xT gain multiplier, about 1.5×) and a lower `keep_bias`, so the search prefers a vertical ball over keeping possession;
- `max_evals` 32 → 16, because the right answer is usually "forward, now". That also saves time.

**Shot-volume floor:**
- If the score is level, we are in the final third, and we have not shot for about 300 ticks, accept any shot from 10-16 units with **0 or 1 bodies in the lane**.
- The lane count is the same 5-opponent point-to-line test as in `_xgemp.py`.

**Cost:** a few dozen floating-point operations per tick.

**Gate:**
- the 41-150 opponent bands on the ladder;
- target: 0-0 count down, points ≥ +0.03 per match.

#### R2 — Population-calibrated shot model (data, not hand rules)

*Basis:* "expected goals" models fitted on real shot outcomes. plan.md notes that data-driven changes worked where hand rules did not.

**What our model does now:**
- `shot_value_from` sets q = 1 if no opponent can reach the ball path before the line;
- otherwise q is a logistic of the margin;
- `GOAL_W` (fitted on our own logs) exists but is switched off (`learned_goal: 0`).

**Fix:**
1. Fit `GOAL_W` on **ladder replays from many teams**. Every ladder replay is public through `api/replay?name=ladder/<id>`.
   - Stream about 300 replays (download, extract shots, delete; about 8 MB each).
   - Recompute our own features (margin, gt, speed, distance, |y|) with team.py's `ball_path` and `first_intercept`.
   - Add one new feature, **bodies in lane**.
   - Fit with `lab/fit.py`.
2. Runtime cost: unchanged (one dot product).
3. Turn on `learned_goal: 1` only if the paired local test is neutral or better, then test on the ladder.

**Risk:** plan.md records a keep-model refit at zero. The goal model has never been fitted on *other* teams' keepers, and those are what we actually shoot against.

#### R3 — Score-state play: "all-in when trailing late", "free when decided"

*Basis:* the hockey goalie-pulling literature (Beaudoin & Swartz 2010, *Strategies for pulling the goalie in hockey*; Asness & Brown 2018, *Pulling the Goalie*). Both find that teams should take the high-variance option **earlier** than intuition says, because conceding again when already losing costs little.

**Our case is cleaner than hockey:**
- When we trail by 1 late, **conceding a second goal costs 0 points**. A loss is a loss.
- So every action that raises our chance of equalising is free.

**Trailing late** (`sg < so` and `time_remaining < 0.15`):
- the keeper joins the attack as a fifth outfielder (target: the edge of their box);
- defenders push to the halfway line;
- `gs_chase` stays on top of this.
- We have **105 matches lost 0-1**. Lifting the late-equaliser rate by 5 points is about +5 points, for almost no work.

**Decided** (trailing by ≥ 2 with `time_remaining < 0.2`, or leading by ≥ 3):
- switch to the W-style cheap path (fixed positions, cheap clearance or a single shot), whatever the score;
- **this is pure decision-time saving**, because the result essentially cannot change.

#### R4 — Angle-coverage defence (an SSL standard; the algorithmic form of D1)

*Basis:* RoboCup Small-Size-League defence.
- Defenders are placed to cover the **largest uncovered angular interval** of the goal as seen from the ball, not at fixed offsets.
- This is the shadow/coverage approach in SSL team papers such as TIGERs Mannheim and ER-Force, and in the goalkeeper review arXiv 2303.12635.

**Algorithm (O(5)):**
1. From the ball, the goal spans the angle interval [θ(−7), θ(+7)].
2. Each of our bodies at distance d covers about ±asin((r + r_ball + 0.3)/d) around its bearing.
3. Merge the covered intervals and find the largest gap.
4. Send the nearest free defender to the gap's bisector, 3-5 units from the ball.

**Use it in two places:**
- `defence_plan` (replaces the fixed `cover_dist` target when the carrier is within 30 units);
- the W wall, where slots are placed to close gaps rather than at fixed spacing. That is also what Team-034's ball-side shift approximates.

This directly targets our 1.09 shots blocked per match.

#### R5 — Opponent-style switch (more of what already worked)

*Basis:* opponent modelling in robot soccer (for example Riley & Veloso's SSL opponent-strategy learning). In our own history, `dom_mode` and `bus_mode` detection paid off where hand rules did not.

**Add a third detector, "possession opponent":**
- triggered when the opponent's touch or kick rate over the last ~400 ticks is high and our territory is under 0.5;
- in that mode, apply R1's counter-window parameters permanently, so we play direct.
- Team-008 (159 kicks to our 85) and Team-009 are exactly this type.

**Cost:** one counter updated per tick.

#### R6 — Learned formation table (HELIOS-style Delaunay triangulation)

*Basis:*
- HELIOS (Akiyama & Noda; RoboCup 2D champions; `github.com/helios-base`) defines formation as a **function of ball position**;
- the function is a set of (ball position → 5 player positions) samples, triangulated (Delaunay), and **linearly interpolated** inside the triangle containing the ball.

**Why it is interesting for us:**
- Lookup is O(1): find the triangle, then three weighted sums. It could replace the pitch-control `support_plan` (refreshed every 6 ticks), which is one of our more expensive parts.
- The samples can be **learned from the top teams' replays**. Take Team-248 and Team-053 frames (0.07-0.10 ms teams with GA ≈ 0.0-0.2 against mid-table teams), cluster their off-ball positions by ball cell, and store about 60 sample points.

**Verdict:** too big to finish and ladder-test before 2026-10-27. Only do it if the ladder or grading window turns out to be longer.

#### R7 — Further decision-time ideas (checked against the code)

**Already done well:**
- `ball_path` is exact, with early exits;
- reach uses precomputed tables (`GT`, `FPOW`, `SPD`, `DREST`, `AD`);
- interception scans break as soon as a rival beats the best found so far;
- plan reuse (`reuse_k` 3) and an anytime search with a 12 ms guard.

**What is left:**
1. **Skip pitch control when it cannot matter.** Skip `support_plan`'s pitch-control pass (`pc_*`) when W, a decided state or our own deep build-up applies; use the default spots there. Profile with `lab/timing.py --profile` to see its share first.
2. **Search budget tied to state.** Use `max_evals` 32 only in the attacking third or in the counter window, and 16 in our own half, where the choice is almost always "safe pass or clear".
   - Earlier history: `max_evals` 24 with `reuse_k` 5 cost no points but saved little.
   - A *state-dependent* cap concentrates the savings where they are free.
3. **Cache across ticks the per-opponent `first_intercept` results** while ball velocity is unchanged (free ball, no kick since the last tick). Each tick's path is just the previous one shifted by one. Plan reuse partly does this already.
4. Do **not** lower the 12 ms guard (plan.md: the 6 ms guard regressed play).

### 11.3 How this changes the schedule

- **U1 (W)** and **U2 (D, preferably in the R4 angle-coverage form)** stay as in §7.
- **U3 = R1 + R5** (counter window + possession-opponent switch). It targets the 104 0-0 draws, the largest single pool of lost points we have found.
- **R3** is small and isolated. It can ride along with U1 *only* if U1 is late. Otherwise add it to U3, because its effect cannot be confused with R1's (it only acts in the last 15% of the match while trailing).
- **R2** fitting can run in the background today (a downloader script), and becomes U3's alternative if R1 fails its gate.
- **R6** is post-deadline work.

### 11.4 Revised points estimate

| Lever | Pool of points | Estimate |
|---|---|---|
| W (wall when leading) | ~30-35 lost leads | +50-80 |
| R1 + R5 (counter window, direct play against possession teams) | 104 0-0s (41-150 bands) + 0-0s against 61-100 | +30-80 |
| D/R4 (angle-coverage screen) | 0-1 / 0-2 losses | +0-40 |
| R3 (all-in late) | 105 0-1 losses | +3-8 |
| R3 + R7 + W (decision time) | — | 0.60 → about 0.30-0.35 ms |

- **Total:** about +80 to +200 points. **Division 3 (≈ 2171) is likely if W lands. Division 2 (≈ 2441) needs nearly everything to work** and remains a stretch.

### 11.5 Side note: the weekly Cup

`api/cup` shows a 20-team knockout every Sunday:
- the next one is today at 19:00 SAST;
- past winners include Team-003, Team-011 and Team-160.

I did not determine how teams qualify, and it does not affect ladder points. The 1-0-then-wall approach (W) is exactly the style that wins knockouts, so it is worth knowing if we qualify.

### 11.6 New evidence files

| Type | File | Contents |
|---|---|---|
| Script | `_bandcmp.py` | band-by-band points per match, for any team |
| Script | `_zz.py` | our 0-0 opponents and the top teams' records against them |
| Script | `_shotan.py` | per-replay possession, final-third entries, shots and lane bodies |
| Script | `_xgemp.py` | empirical shot outcomes across all downloaded replays |
| Output | `_shot1.txt` | us / Team-034 / Team-248 vs Team-008 |
| Output | `_shot2.txt` | us / Team-034 / Team-248 vs Team-009 |
| Output | `_gtl4.txt` | goal build-ups from those matches |
| Output | `_xgemp.txt` | the shot-outcome table above |

**Key replays:**

| Replay | What it shows |
|---|---|
| `m-155515a7b6c5ea0c` | us 0-0 Team-008 (0 shots) |
| `m-a10e3ddbf39b36ec` | Team-248 5-0 Team-008 (transition long shots) |
| `m-40c6bc3c2d79fcab` | Team-034 1-0 Team-008 (switch, then a finish from 10 units) |
| `m-4d10b9a4869aa0d9` | Team-034's wall holds against 24 shots from Team-009 |
| `m-b12f0f8480493628` | us 0-0 Team-009 (2 shots) |


---

## 12. Status (Claude, 2026-10-25)

* **W tested locally** (paired vs cand65, style pool, 180–270 matches each):
  wall at any lead −0.12 ± 0.05 points/match (concedes +0.11); with the
  kick search instead of clearances −0.33; 1-goal lead late only +0.04 then
  −0.10 on a second seed set. Only **wall from 2 up** is points-neutral
  (0 results changed in 450 matches) and it halves decision time against
  beatable teams (0.32 → 0.16 ms). Packaged as **cand66** (`lab/cand66.py`,
  installed as `my-team/team.py`). Details: plan.md §30.
* **R1 (counter window)** built as switches in `lab/teams/v67.py` and **rejected**: −0.24 ± 0.09, −0.13 ± 0.09, −0.24 ± 0.10 points per match for the three variants (plan.md §31).
* **R2 not done as written**: streaming ~300 replays of other teams'
  matches to disk is the data handling we agreed to avoid; any refit would
  have to run in the browser, keeping only aggregate shot features.
* T1 note: `reuse_k 5` alone measured −0.43 ± 0.15 vs selfkeep (plan.md
  §16), not "no points change".

---

## 13. Plan from here (after U1 = cand66 on the ladder, 2026-10-25)

### 13.1 Where cand66 landed

- Rank 76, Div 4, 2045 points / 1012 matches (2.021 per match), **0.503 ms** (was 0.603), 2 timeouts.
- Paired against unchanged opponents (876 fixtures, `lab/_pair2.py`): **points +0.000 per match**. The wall at 2 goals is points-neutral and cheaper, so keep it.
- The `wall_late` 0.5 idea is dropped: +0.04 on one seed set, −0.10 on the second (§12).

### 13.2 The key fact: inside a division, rank = decision time

Div 4 is ordered by mean decision time, not points (Team-152, 1949 points, is rank 61 at 0.078 ms). Points only matter for crossing a division boundary.

| Boundary | Points per match | Our margin |
|---|---|---|
| Div 3 floor (Team-071) | 2.149 | −0.13 (need ≈ +130 points) |
| Div 5 top (≈ Div 4 floor) | 1.870 | +0.15 |

No lever left in this plan has a measured gain anywhere near +0.13 per match. A speed gain, though, moves us up for certain:

| Our mean ms | Div 4 position | Rank |
|---|---|---|
| 0.503 (now) | 16 | 76 |
| < 0.49 | 15 | 75 |
| < 0.389 | 10 | 70 |
| < 0.266 | 9 | 69 |
| < 0.221 | 6 | 66 |
| < 0.206 | 5 | 65 |

**So the main track is decision time.** A points cost of up to about −0.05 per match is acceptable, because it cannot drop us a division. Earlier speed variants were rejected for costing −0.02 to −0.06 points per match. That reasoning applied when we were near the Div 3 line, and it no longer holds.

### 13.3 Where the time goes (cand66 vs elite, seed 1001, cProfile; `lab/_prof66.txt`)

| Part | Share of `decide` | Note |
|---|---|---|
| `choose_kick` (+ `evaluate` / `try_t`) | ≈ 23% | 56 calls, ≈ 5.5 ms each: the p99 spikes |
| `support_plan` → `pc_assign` | ≈ 17% | 159 calls, ≈ 1.5 ms each (`pc_every` 6) |
| `decide` body itself | ≈ 12% | per-tick overhead |
| `wall` | ≈ 11% | 1073 ticks in a 2-0 match |
| `anticipate` | ≈ 10% | 39 calls, ≈ 3.4 ms each |

Timings: p50 0.22 ms, but 55 ticks over 5 ms. The mean is driven by the kick-search spikes and pitch control, not by ordinary ticks.

### 13.4 Track 1 — speed package (U2), each as a switch on cand66 → v68

| Id | Change | Expected saving | Prior evidence |
|---|---|---|---|
| S1 | `reuse_k` 5 + `max_evals` 24 | ≈ −19% | plan.md §16: −0.02 ± 0.06 points per match, 0.31 → 0.25 ms |
| S2 | `pc_every` 6 → 12 (pitch control half as often) | ≈ −8% | untested |
| S3 | `max_evals` 16 when the kicker is in our own half (32/24 elsewhere) | ≈ −8% | 16 evaluations agree with 32 on 61% of picks (plan.md); own-half picks matter least |
| S4 | Decided state: trailing by ≥ 2 with `time_remaining < 0.2` → wall-style cheap path | small | result cannot change |
| S5 | Wall micro-cuts: cache slot targets, run `wall_clear` only for the kicker | ≈ −3-5% | wall is 11% in leading matches |

**Gate for each switch** (local, paired vs cand66, ≥ 270 matches, the same style pool as §12):
- points ≥ −0.05 per match;
- `lab/timing.py` mean down; p99 < 12 ms; no extra timeouts.

Stack the switches that pass. Target: ≈ 0.30 ms on the ladder (rank ≈ 70); stretch ≈ 0.22 ms (rank ≈ 66).

### 13.5 Track 2 — free points only

- **R3a, all-in when trailing late:** `sg < so` and `time_remaining < 0.15` → keeper to the edge of their box, defenders to halfway, `gs_chase` on top. Conceding again costs 0 points, because ranking uses points, not goal difference. Pool: 105 losses at 0-1. Ride along with U2 if its local paired result is ≥ 0.
- **Not pursued before close:**
  - D/R4 (defensive tweaks have a history of measuring zero or negative);
  - A (the 0-0 opponents press; they are not walls);
  - R1/R5 (rejected locally);
  - R2 (data-handling constraint);
  - R6 (too big).

### 13.6 Schedule

| When | Step |
|---|---|
| Oct 25 (today) | Build v68 = cand66 + S1–S5 + R3a switches (all off). Run timing and paired sweeps. The Cup at 19:00 uses cand66, which is fine. |
| Oct 26 morning | Upload U2 = cand66 + passing switches. Log it in `lab/ladder_log.md`; snapshot `_us3.json` / `_table3.json` after the run. |
| Oct 26 evening | Read the run: mean ms down, and points paired vs unchanged opponents ≥ −0.05. If worse (points or timeouts), re-upload cand66. Otherwise S4/S5 can follow as U3 if they were held back. |
| Oct 27 | No new ideas. Re-upload only to restore the best measured version, and leave enough time for the run to finish. |

### 13.7 Results (Claude, 2026-10-25 afternoon)

* S1+S2+S3 stack: **−0.56 ± 0.08** points/match (270 paired). Individually:
  S3 (max_evals 16 in own half) **−0.51 ± 0.07**; max_evals 24 −0.16 ± 0.08;
  S2 (pc_every 12) +0.06 ± 0.09 with −8% time. The −0.05 allowance rules out
  everything except S2. Own-half kick decisions are where search depth pays.
* R3a + S4: 0.00 ± 0.01 (harmless).
* **U2 = cand68** = cand66 + S2 + R3a + S4: fresh seeds 0.00 ± 0.09 points,
  7–9% faster. Installed as `my-team/team.py`. S5 skipped (small).
* Note on cand66: paired vs the cand59 snapshot it conceded +51 goals in 616
  matches (the 2-0 wall leaks against real teams) — points within noise.

---

## 14. The one big lever left: play for the win when level late (2026-10-26)

### 14.1 Status after U2 (cand68 = cand66 + pc_every 12 + all-in when trailing + decided path)

- Ladder row: rank 73, Div 4, 1792 points / 920 matches (1.948 per match), 0.479 ms, 20 timeouts.
- 142 opponents re-uploaded and 9 new teams joined, so the whole field moved: Div 3 floor 2.149 → **2.027** per match, Div 4 range 1.74-2.00.
- Paired vs cand66 on the 484 unchanged fixtures (`lab/_pair3b.txt`): **+0.014 per match**, GA 0.41 → 0.39. Neutral, as measured locally. Keep it.
- Gap to Div 3 is now **0.08 per match ≈ 75 points**, smaller than yesterday.
- Speed is exhausted: S1/S3 cost −0.16 to −0.56 per match (plan.md §32); only S2 passed.

### 14.2 Why the draws are the only pool big enough

| Result | Matches per run | Points now |
|---|---|---|
| 0-0 | 141 | 141 |
| 1-1 | 49 | 49 |
| total level at the end | **190** | 190 |

Under 3-1-0 scoring a draw turned into a win is **+2** and a draw turned into a loss is **−1**. Pushing when level pays as long as we create more than one extra win per two extra losses. Illustration: if a late push converts 25% of the 190 to wins and 15% to losses, that is +95 − 28 = **+67 points ≈ +0.07 per match**, the whole Div 3 gap. No other lever has a pool this size: the 0-1 losses (91) are mostly to the top 60, where we create nothing.

Evidence that the games are on a knife edge: between two runs of near-identical code, 1-0 ↔ 0-0 flipped 30 times and 0-0 ↔ 2-0 15 times among 484 fixtures. One chance decides them, so more late chances is the right currency. Our shot volume is the symptom: 2.2-3.0 shots per match against the local sty_* pool, versus 4.3-8 against teams we beat.

### 14.3 Build (switches on cand68 → v69, all off by default)

1. **`allin_level_t`** (e.g. 0.10): the existing all-in overlay (`allin_mode`, keeper up as a fifth outfielder, `rear_depth` 5) also fires when `sg == so` and `time_remaining < allin_level_t`. One condition change at the `self.allin =` line.
2. **`gs_push`** overlay for `sg == so` and `time_remaining < gs_push_t` (e.g. 0.20), applied after `gs_chase`: `goal_units` 3.0, `keep_bias` 0.6, `lose_pen` 0.0, `shot_range` 36, `la_k` unchanged. Add `push` to the `mode_cache` key.
3. **Shot-volume floor** when level in the last 20%: in `choose_kick`, accept a shot from ≤ 16 units with ≤ 1 body in the lane if no shot in the last 300 ticks (the 10-15 unit, ≤ 1 body band scores 33-80% in `_xgemp.txt`).

Grid to run tonight (paired vs cand68, style pool, 270 matches each): `allin_level_t` ∈ {0.10, 0.20}; `gs_push_t` ∈ {0.20, 0.35}; floor on/off. Read **points**, not goal difference: GA will rise and that is expected.

### 14.4 Gate and risk

- Upload only the best cell if it is ≥ +0.03 per match with the error bar not crossing zero on the sty_* and v48cap opponents (the ones that draw with us locally).
- The downside is bounded: worst case a draw becomes a loss (−1). It cannot touch the 2-0 wall games or the top-60 losses.
- Timing: the run that started 19:35 UTC on Oct 26 ends around 01:00 UTC. Upload v69 before the next run starts, keep `lab/submitted_c68.py` as the fallback, and re-upload cand68 if the paired result on unchanged opponents is below −0.03.
