"""Writes lab/teams/block.py and lab/teams/dribbler.py from keepball.py
(one controller class per file, as the loader wants), changing only the
class attributes."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "teams", "keepball.py")).read()
base = src.split("\n\nclass Block(KeepBall):")[0].rstrip("\n") + "\n"
V = {
    "block": dict(LINE_BACK=14.0, LINE_MIN=-36.0, LINE_MAX=-14.0, FWD=0.6, SAFE=1.0, SHOOT=22.0),
    "dribbler": dict(LINE_BACK=6.0, LINE_MIN=-25.0, LINE_MAX=10.0, KEEPER_DEPTH=8.0, FWD=1.4,
                     SAFE=0.0, SHOOT=30.0, PRESS2=True),
}
for name, over in V.items():
    s = base.replace('name = "keepball"', 'name = "%s"' % name)
    for k, v in over.items():
        lines = s.split("\n")
        for i, l in enumerate(lines):
            if l.startswith("    %s = " % k):
                comment = l[l.index("#"):] if "#" in l else ""
                lines[i] = ("    %s = %r" % (k, v)) + ("       " + comment if comment else "")
                break
        else:
            raise SystemExit("no attribute " + k)
        s = "\n".join(lines)
    open(os.path.join(HERE, "teams", name + ".py"), "w").write(s)
open(os.path.join(HERE, "teams", "keepball.py"), "w").write(base)
print("ok")
