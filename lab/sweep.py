"""Parameter sweeps: score team variants against an opponent pool.

    py -3 lab/sweep.py --base v3 --grid '{"react": [0, 1, 2]}' --vs lab/teams/v1.py elite --seeds 1000..1019

Every variant plays every opponent on every seed from both ends. One shared
process pool runs all fixtures. Prints points (3/1/0), W-D-L and goal
difference per variant, best first.
"""

import argparse
import hashlib
import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer.runner import _build_fixtures, _run_fixture  # noqa: E402

TEMPLATE = '''import os, sys
sys.path.insert(0, {teams!r})
from {base} import MyTeam as _Base


class MyTeam(_Base):
    name = "{name}"

    def __init__(self):
        super().__init__()
        self.p.update({over!r})
'''


def parse_seeds(text):
    if ".." in text:
        a, b = text.split("..")
        return list(range(int(a), int(b) + 1))
    return [int(s) for s in text.split(",")]


def job(args):
    team, opp, fixture, timeout = args
    r = _run_fixture(team, opp, fixture, None, None, None, timeout, None)
    return team, opp, r["score"][0], r["score"][1], r.get("platform_error")


def make_variants(base, overrides):
    os.makedirs(os.path.join(HERE, "variants"), exist_ok=True)
    paths = []
    for i, over in enumerate(overrides):
        tag = "_".join(f"{k}{v}" for k, v in over.items()) or "base"
        tag = "".join(c if c.isalnum() or c in "_." else "-" for c in tag)[:40]
        # The readable prefix can collide; the hash of the full overrides cannot.
        tag += "_" + hashlib.sha1(json.dumps(over, sort_keys=True).encode()).hexdigest()[:10]
        name = f"{base}__{tag}"
        path = os.path.join(HERE, "variants", name + ".py")
        with open(path, "w") as fh:
            fh.write(TEMPLATE.format(teams=os.path.join(HERE, "teams"), base=base,
                                     name=name, over=over))
        paths.append((path, over))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--grid", default="{}", help="JSON dict of param -> list")
    ap.add_argument("--list", default=None, help="JSON list of override dicts")
    ap.add_argument("--vs", nargs="*", required=True)
    ap.add_argument("--seeds", default="1000..1019")
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=1000.0)
    a = ap.parse_args()
    if a.list:
        overrides = json.loads(a.list)
    else:
        grid = json.loads(a.grid)
        keys = list(grid)
        overrides = [dict(zip(keys, vals)) for vals in itertools.product(*(grid[k] for k in keys))]
        if not overrides:
            overrides = [{}]
    variants = make_variants(a.base, overrides)
    seeds = parse_seeds(a.seeds)
    jobs = [(path, opp, fx, a.timeout) for path, _ in variants for opp in a.vs
            for fx in _build_fixtures(seeds, True)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(job, jobs, chunksize=1))
    table = []
    for path, over in variants:
        rs = [r for r in rows if r[0] == path]
        w = sum(1 for r in rs if r[2] > r[3])
        d = sum(1 for r in rs if r[2] == r[3])
        l = sum(1 for r in rs if r[2] < r[3])
        gd = sum(r[2] - r[3] for r in rs)
        per = {}
        for opp in a.vs:
            ro = [r for r in rs if r[1] == opp]
            per[os.path.basename(opp)] = "%d-%d-%d" % (
                sum(1 for r in ro if r[2] > r[3]), sum(1 for r in ro if r[2] == r[3]),
                sum(1 for r in ro if r[2] < r[3]))
        table.append((3 * w + d, gd, w, d, l, over, per))
    table.sort(key=lambda t: (-t[0], -t[1]))
    for pts, gd, w, d, l, over, per in table:
        print(f"{pts:4d} pts  {w:3d}-{d:3d}-{l:3d}  GD {gd:+4d}  {json.dumps(over)}  {per}")
    print(f"wall {time.time() - t0:.0f}s, {len(rows)} matches")


if __name__ == "__main__":
    main()
