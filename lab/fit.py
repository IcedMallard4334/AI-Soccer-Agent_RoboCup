"""Fit logistic models for keep / goal probability from lab/kicklog.json.

Prints the calibration of the current hand-set curves, then the fitted
coefficients (Newton's method, small L2), and their calibration.

    py -3 lab/fit.py [lab/kicklog.json]
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def keep_x(r):
    _, margin, mt, sp, rx, free, _y = r
    m = max(-15.0, min(15.0, margin))
    return [1.0, m / 10.0, free, min(mt, 80.0) / 20.0, sp / 20.0, rx / 50.0, (m / 10.0) * (sp / 20.0)]


def goal_x(r):
    _, margin, gt, sp, bx, by, _y = r
    m = max(-15.0, min(15.0, margin))
    d = math.hypot(50.0 - bx, by)
    return [1.0, m / 10.0, min(gt, 80.0) / 20.0, sp / 30.0, d / 30.0, abs(by) / 30.0]


def sig(z):
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def fit(X, y, l2=1e-3, iters=25):
    n = len(X[0])
    w = [0.0] * n
    for _ in range(iters):
        g = [0.0] * n
        H = [[0.0] * n for _ in range(n)]
        for xi, yi in zip(X, y):
            z = sum(a * b for a, b in zip(w, xi))
            p = sig(z)
            e = p - yi
            s = p * (1 - p) + 1e-6
            for a in range(n):
                g[a] += e * xi[a]
                xa = xi[a] * s
                Ha = H[a]
                for b in range(a, n):
                    Ha[b] += xa * xi[b]
        for a in range(n):
            g[a] += l2 * w[a] * len(X)
            H[a][a] += l2 * len(X)
            for b in range(a):
                H[a][b] = H[b][a]
        step = solve(H, g)
        w = [wi - si for wi, si in zip(w, step)]
        if max(abs(si) for si in step) < 1e-6:
            break
    return w


def calib(pred, y, label):
    bins = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.97, 1.01]
    print("  %s:" % label)
    for lo, hi in zip(bins, bins[1:]):
        idx = [i for i, p in enumerate(pred) if lo <= p < hi]
        if idx:
            print("    pred %.2f-%.2f  n=%5d  mean pred %.3f  actual %.3f" % (
                lo, hi, len(idx), sum(pred[i] for i in idx) / len(idx), sum(y[i] for i in idx) / len(idx)))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "kicklog.json")
    rows = json.load(open(path))
    keep = [r for r in rows if r[0] == "k"]
    goal = [r for r in rows if r[0] == "g"]
    # Current curves (v41 defaults).
    kb, sk, gb, sg = 1.951, 4.363, 2.846, 2.141
    print("keep rows", len(keep))
    calib([sig((r[1] - kb) / sk) for r in keep], [r[6] for r in keep], "current keep curve")
    Xk = [keep_x(r) for r in keep]
    yk = [r[6] for r in keep]
    wk = fit(Xk, yk)
    print("  KEEP_W =", [round(v, 4) for v in wk])
    calib([sig(sum(a * b for a, b in zip(wk, x))) for x in Xk], yk, "fitted keep")
    print("goal rows", len(goal))
    calib([sig((r[1] - gb) / sg) for r in goal], [r[6] for r in goal], "current goal curve")
    Xg = [goal_x(r) for r in goal]
    yg = [r[6] for r in goal]
    wg = fit(Xg, yg, l2=3e-3)
    print("  GOAL_W =", [round(v, 4) for v in wg])
    calib([sig(sum(a * b for a, b in zip(wg, x))) for x in Xg], yg, "fitted goal")
    json.dump({"keep": wk, "goal": wg}, open(os.path.join(HERE, "fit_weights.json"), "w"))


if __name__ == "__main__":
    main()
