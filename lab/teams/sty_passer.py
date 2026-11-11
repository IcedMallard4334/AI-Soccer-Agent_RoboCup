"""Style opponent (plan.md 22): our own engine (v61) with a different
personality - pass-first: no safe dribbling, few dribble candidates."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v61 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sty_passer"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32})
        self.p.update({'sd_on': 0, 'c_drib_n': 4, 'c_carry_n': 0})
        self.p.update(json.loads(os.environ.get("STY_P", "{}")))
