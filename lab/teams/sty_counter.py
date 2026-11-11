"""Style opponent (plan.md 22): our own engine (v61) with a different
personality - sits deep, marks tight goal-side, breaks with long balls."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v61 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sty_counter"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32})
        self.p.update({'rear_depth': 30.0, 'cover_dist': 20.0, 'mark_goal_side': 3.0, 'sd_on': 0, 'c_through': (16.0,), 'shot_range': 30.0})
        self.p.update(json.loads(os.environ.get("STY_P", "{}")))
