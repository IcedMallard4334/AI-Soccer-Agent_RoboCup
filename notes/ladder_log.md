# Ladder log (one row per upload)

Ladder: 239 teams, 916 matches each on seeds 1000–1003, both ends. Division =
top 20 on points; order inside a division = mean decision time.

| Date (UTC) | Build | Points | W-D-L | GF-GA | Mean ms | Timeouts | Rank / Div | Div 1 floor |
|---|---|---|---|---|---|---|---|---|
| 2026-10-23 17:15 | v38-era (last upload before v54) | 2067 | 643-138-135 | 2470-304 | 1.80 | 332 | 60 / 3 | ≈2391 |
| 2026-10-23 20:13 | v57 (v51 decisions + speed, 6 ms guard) | 2036 (948 m) | 625-161-162 | 2237-328 | 0.78 | 48 | 58 / 3 | 2485 (Div 2: 2184) |
| 2026-10-24 16:05 | v57 unchanged (others re-uploaded) | 1976 (948 m) | 609-149-190 | 2127-377 | 0.72 | 43 | 80 / 4 | 2518 (D2 2221, D3 2003, D4 1746) |

Buckets for that run (opponent rank: W-D-L): 1–20 3-10-67 · 21–40 18-27-35 ·
41–80 75-55-26 · 81–150 228-45-7 · 151+ 319-1-0.

v57 buckets (W-D-L, points/match): 1–20 0-11-69 (0.14) · 21–40 17-18-45
(0.86) · 41–80 63-54-39 (1.56) · 81–150 205-69-6 (2.44) · 151+ 340-9-3 (2.92).
0-0 draws 129 (was 92). Points/match 2.148 (was 2.257) while the division
floors per match barely moved, so v57 is ≈ 100 points worse on a like field.
Server factor ≈ 2.2× (0.78 ms vs ≈ 0.35 ms local).

Likely cause: the 6 ms guard. At the server-equivalent local budget
(2.7 ms) 26% of kick searches stop before 28 evaluations and some get none
(a blind forward kick); local tests all ran without a guard.

Paired snapshot of v57's own results (hashed opponent ids, opponent
last_updated, seed, side, score) is kept in the browser's localStorage for
lamp.ms.wits.ac.za under `vh_snapshot_v57`, for match-by-match comparison
of the next upload against opponents that did not change.

Next row: v58 = v57 with a 12 ms guard (only change; 5% of searches cut at
the server-equivalent budget, as with no guard).

2026-10-24 re-run, same v57 code, compared match by match with the snapshot:
524 matches vs opponents that had not re-uploaded: identical (CACHED: only
a new upload's matches are played, so this says nothing about determinism). 380 matches vs 95 re-uploaded opponents: 736 -> 638 points
(-98). 44 new entrants replaced 44 departed (+101 vs +62). The drop to
Div 4 is the field improving, not our team changing; v58 had not been
uploaded. Div 3 floor 2003 (27 above us).

| 2026-10-24 17:05 | v58 (v57 + 12 ms guard) | 2018 (988 m, run in progress) | 613-179-196 | 2198-409 | 0.63 | 5 | 79 / 4 | 2551 (D2 2296, D3 2078) |

v58 vs v57, paired on 500 matches against opponents unchanged since the v57
snapshot: points 1188 vs 1181 (+7, about ±29), goals for 1556 vs 1477
(+0.16/match), against 119 vs 120, W-D-L 369-81-50 vs 372-65-63. The guard
fix is real but small on the ladder (+0.01 points/match), far below the
+0.31 measured locally at "server-equivalent" budgets — the server does not
truncate the search the way 2.7 ms locally does. Snapshot of v58 results:
localStorage `vh_snapshot_v58`. Next upload: cand59 (passing), now installed
as my-team/team.py; v58 saved as lab/submitted_v58.py.

| 2026-10-24 17:51 | cand59 = v59 (v58 + keep-model speed terms off: passing) | 2063 (984 m) | 633-164-187 | 2133-380 | 0.62 | 29 | 58 / 3 | 2534 (D2 2283, D3 2040) |

cand59 vs v58, paired on 928 matches against unchanged opponents: points
1940 vs 1910 (+0.032 ± 0.038 per match), W-D-L 595-155-178 vs 579-173-176,
0-0 draws 120 vs 128, goals for 2038 vs 2091, against 359 vs 367. Every rank
bucket slightly positive. Same as the local estimate (+0.03 ± 0.06): a small
gain inside the noise. Back in Div 3 (23 points above its floor). Snapshot:
localStorage `vh_snapshot_c59`.

| 2026-10-24 19:24 | cand62 = cand59 + bus -> direct detection | 2068 (996 m, run in progress) | 632-172-192 | 2170-426 | 0.65 | 10 | 58 / 3 | 2565 (D2 2313, D3 2068) |

cand62 vs cand59, paired on 884 matches against unchanged opponents: points
1846 vs 1861 (-0.017 ± 0.024 per match), goals for 2004 vs 1983, against
369 vs 346, W-D-L 563-157-164 vs 572-145-167. Only 122 of 884 results
changed at all (the switch only acts when the detector fires), and the net
is slightly negative, mostly in ranks 41-80 (-9) and 1-20 (-5). The local
gain against the bus did not show up: real ladder teams either rarely sit
as deep as the bus, or the direct response hurts against those that
trigger it. Snapshot: localStorage `vh_snapshot_c62`.

| 2026-10-24 20:01 | cand59 re-upload | 2042 (984 m, mid-run) | 622-176-186 | 2113-418 | 0.68 | 66 | 59 / 3 | D3 2042 |
| 2026-10-24 21:09 | cand64 = cand59 + keeper 36/16 | 2076 (1000 m, mid-run) | 635-171-194 | 2131-434 | 0.65 | 14 | 79 / 4 | D3 2079, D2 2360 |

cand64 vs cand59 (paired, 796 unchanged-opponent matches): points 1686 vs
1705 (-0.024 ± 0.034), goals against 330 vs 290 (+40), against ranks 1-20
160 vs 141, points vs ranks 21-40 13 vs 25. Same picture vs the cand62
snapshot (852 matches): against 357 vs 339, ranks 21-40 points 14 vs 30.
The gallery keeper (strikes only) concedes more against real top teams,
who also pass across and dribble round a keeper who has come out.
REVERTED to cand59. Snapshot: localStorage `vh_snapshot_c64`.
