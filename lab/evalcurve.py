"""How much of the kick search changes the decision? Captures kick decisions
(lab/kickbench.py's capture), re-runs choose_kick at several evaluation caps
and reports per cap: time per kick, share of decisions identical to the
32-evaluation decision, and the value lost (32-cap value of the 32-cap pick
minus 32-cap value of the cap's pick is not observable; we report how often
the pick differs and the mean drop in the search's own best value).
    py -3 lab/evalcurve.py v54
"""
import copy, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "teams"))
import kickbench  # noqa: E402

mod = __import__(sys.argv[1])
cases = kickbench.capture(mod, seeds=(1001, 1002, 1003))
t = mod.MyTeam()
t.reset(1)


def run(cap):
    outs = []
    t0 = time.perf_counter()
    for args, p, threat in cases:
        t.p = dict(mod.P)
        t.p.update(p)
        t.p["budget"] = 1.0
        t.p["max_evals"] = cap
        t.base_p = t.p
        t.threat = threat
        t.t0 = time.perf_counter()
        a = t.choose_kick(*copy.deepcopy(args))
        outs.append((a.kick_direction, round(a.kick_power, 6), a.movement))
    return (time.perf_counter() - t0) * 1000 / len(cases), outs


base_ms, ref = run(32)
print("%d kick decisions" % len(cases))
for cap in (8, 12, 16, 20, 24, 28, 32, 48):
    ms, outs = run(cap)
    same = sum(1 for a, b in zip(ref, outs) if a == b)
    print("cap %3d  %.2f ms/kick  identical to cap-32 pick %5.1f%%" % (cap, ms, 100.0 * same / len(cases)))
