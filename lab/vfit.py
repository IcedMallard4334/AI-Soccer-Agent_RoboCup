"""Fit a state value: a re-learned position grid plus defensive-context terms.

Rows from lab/vlog.py: (x, |y|, ndef_goalside, natt_ahead, nearest_def, label).
V = grid(x, |y|) + w . [ndef, natt, near, ndef*g, natt*g, near*g]
with g = exp(-dist_to_goal / 15), fitted by least squares on the residual.

    py -3 lab/vfit.py lab/vlog.json
Writes lab/vfit.json (grid 20x6 + weights) and prints the grid and weights.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NX, NY = 20, 6


def feats(x, y, ndef, natt, near):
    g = math.exp(-math.hypot(50.0 - x, y) / 15.0)
    nr = min(near, 15.0) / 15.0
    return [ndef, natt, nr, ndef * g, natt * g, nr * g]


def solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c and abs(M[c][c]) > 1e-12:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def cell(x, y):
    ix = min(NX - 1, max(0, int((x + 50.0) / 5.0)))
    iy = min(NY - 1, int(y / 5.0))
    return ix, iy


def main():
    rows = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "vlog.json")))
    sums = [[0.0] * NY for _ in range(NX)]
    cnts = [[0] * NY for _ in range(NX)]
    for x, y, nd, na, ne, lab in rows:
        i, j = cell(x, y)
        sums[i][j] += lab
        cnts[i][j] += 1
    raw = [[sums[i][j] / cnts[i][j] if cnts[i][j] else 0.0 for j in range(NY)] for i in range(NX)]
    # Count-weighted 3x3 smoothing (lighter at the two goal ends).
    grid = [[0.0] * NY for _ in range(NX)]
    for i in range(NX):
        for j in range(NY):
            num = den = 0.0
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < NX and 0 <= jj < NY and cnts[ii][jj]:
                        w = cnts[ii][jj] * (1.0 if di == 0 and dj == 0 else (0.25 if i in (0, 1, NX - 2, NX - 1) else 0.5))
                        num += raw[ii][jj] * w
                        den += w
            grid[i][j] = num / den if den else 0.0
    # Residual regression on context features.
    n = 6
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for x, y, nd, na, ne, lab in rows:
        i, j = cell(x, y)
        r = lab - grid[i][j]
        f = feats(x, y, nd, na, ne)
        for a in range(n):
            b[a] += f[a] * r
            for c in range(n):
                A[a][c] += f[a] * f[c]
    # Centre features per cell implicitly via a small ridge.
    for a in range(n):
        A[a][a] += 1e-3 * len(rows)
    w = solve(A, b)
    # Variance explained.
    sse0 = sse1 = 0.0
    for x, y, nd, na, ne, lab in rows:
        i, j = cell(x, y)
        e0 = lab - grid[i][j]
        e1 = e0 - sum(a * c for a, c in zip(w, feats(x, y, nd, na, ne)))
        sse0 += e0 * e0
        sse1 += e1 * e1
    print("rows", len(rows), "SSE grid-only %.1f  with context %.1f  (%.2f%% less)" % (
        sse0, sse1, 100.0 * (sse0 - sse1) / sse0))
    print("weights [ndef, natt, near, ndef*g, natt*g, near*g] =", [round(v, 4) for v in w])
    for j in range(NY):
        print("|y|%2d " % (j * 5) + " ".join("%5.2f" % grid[i][j] for i in range(NX)))
    json.dump({"grid": grid, "w": w}, open(os.path.join(HERE, "vfit.json"), "w"))


if __name__ == "__main__":
    main()
