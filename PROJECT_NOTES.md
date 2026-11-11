# Project notes — Soccer team assignment

## Links
- **League standings / leaderboard:** https://lamp.ms.wits.ac.za/soccer/#/standings
- **Full game brief / student guide:** [docs/student-guide.md](docs/student-guide.md) (same text as the course brief)

## Submission
- Hand in **one file**: `my-team/team.py`, uploaded to Moodle. Must keep that name.
- Exactly one `TeamController` subclass; no second `.py` file (helper imports fail on the server).
- Run `START.cmd check` before uploading — same checks the server runs.

## Grading
- Round-robin vs every other team in the class, over a hidden seed set (practice seeds: **1001–1005**), alternating ends.
- Per match: 3 pts win, 1 draw, then goal difference.
- Table cut into **divisions of 20 on points**; inside a division, ranked by **mean decision time (lower is better)**.
- Raising repeatedly / hanging forfeits the match 0-3. 20 consecutive timeouts = forfeit.
- Award for fewest fouls per game.

## Hard limits & rules
- **20 ms per decision** for the whole team (timeout repeats previous action).
- `act(obs)` called 20×/s; must return a `TeamAction` covering every player every tick (use `PlayerAction()` to stand still on purpose).
- `move` / `kick` / `set` each **replace** the player's whole action — use `kick(id, aim, power, movement=run)` to run + kick.
- `initial_formation(field)`: own half (x ≤ 0), inside pitch, outside centre circle. Slot 0 = goalkeeper.
- Only foul: entering centre circle during the **opponent's** kickoff → player sent to far touchline (~4 s). Check `obs.ball.controlling_team` before chasing at restarts.

## Frame & physics (course profile)
- Pitch 100 × 60; your goal (-50, 0), theirs (+50, 0); goal mouth |y| ≤ 7. Always attack +x.
- My ids 0..n-1 (= list indices); opponent ids n..2n-1 (build `{o.id: o for o in obs.opponents}`).
- `kick_impulse` = 22 u/s at power 1.0; ball speed × `ball_friction` (≈0.985) per tick; cap 30 u/s; impulse is **added** to current ball velocity.
- Pass sizing: `power ≈ distance / 33` (arrives ~2 s). Power ≥ 0.5 = strike/pass; < 0.5 = touch/dribble.
- Kick needs `obs.can_kick(id)` (in `kick_range` and off cooldown).

## Commands (Windows: `START.cmd <args>`)
```
START.cmd validate my-team
START.cmd play my-team --against balanced
START.cmd play my-team --against balanced --replay replays/game.rep --debug-overlays
START.cmd tournament my-team --seeds 1000..1020
START.cmd baselines
START.cmd doctor
START.cmd check
```

## Opponents (weakest → strongest)
do_nothing, random_legal, ball_chaser, structured_attack, man_marking, possession, balanced (reference), tactical (strongest — a draw is good).
- `possession`: study for **leading passes**.
- `tactical`: ranks shots/passes by lane room, demands more room for longer passes, steers around bodies.
