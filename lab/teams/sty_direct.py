"""Style opponent (plan.md 22): our own engine (v61) with a different
personality - long fast balls in behind, no dribbling."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v61 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sty_direct"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32})
        self.p.update({'sd_on': 0, 'c_drib_n': 4, 'c_vends': (12.0,), 'c_through': (14.0,), 'c_leads': (0.0, 1.2)})
        self.p.update(json.loads(os.environ.get("STY_P", "{}")))
