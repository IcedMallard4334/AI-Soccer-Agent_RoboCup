"""Defensive shape of each opponent: while we have the ball, where do their
four outfielders stand (x in our attacking frame, sorted from the one
nearest our goal)? Also how often all four are past a line L (a block).
    py -3 lab/blockstat.py lab/teams/selfkeep.py elite ...
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style  # noqa: E402

LINES = (0.0, 5.0, 10.0)


def one(args):
    opp, seed, swap = args
    a = style.load("lab/teams/v62.py", {"det_on": 1, "press_on": 2.0})
    b = style.load(opp)
    env = style.SoccerEnv(per_decision_timeout_ms=1000)
    if b is None:
        env.use_baseline(1, opp)
    a.reset(seed)
    if b is not None:
        b.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=1 if swap else 0)
    sums = [0.0] * 4
    past = [0] * len(LINES)
    n = 0
    while not env.finished:
        o = obs["team_a"]
        if o.ball.controlling_team == 0 and o.tick % 5 == 0:
            xs = sorted(q.position[0] for q in o.opponents[1:])
            for i in range(4):
                sums[i] += xs[i]
            for j, L in enumerate(LINES):
                past[j] += xs[0] >= L
            n += 1
        acts = {"team_a": a.act(o)}
        if b is not None:
            acts["team_b"] = b.act(obs["team_b"])
        obs, _ = env.step(acts)
    return opp, sums, past, n


if __name__ == "__main__":
    jobs = [(o, s, w) for o in sys.argv[1:] for s in (9800, 9801) for w in (False, True)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = list(pool.map(one, jobs))
    for o in sys.argv[1:]:
        S = [0.0] * 4
        P = [0] * len(LINES)
        N = 0
        for oo, sums, past, n in res:
            if oo == o:
                S = [a + b for a, b in zip(S, sums)]
                P = [a + b for a, b in zip(P, past)]
                N += n
        N = max(N, 1)
        print("%-16s outfield x (nearest our goal first) %s   all four past x=0/5/10: %s" % (
            os.path.basename(o), " ".join("%5.1f" % (v / N) for v in S),
            " ".join("%3.0f%%" % (100.0 * p / N) for p in P)))
