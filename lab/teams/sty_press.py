"""Style opponent (plan.md 22): our own engine (v61) with a different
personality - presses high with two men and reads passes early."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v61 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sty_press"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32})
        self.p.update({'press2_x': 50.0, 'press2_gap': 25.0, 'antic_t': 10.0, 'cover_dist': 8.0, 'mark_goal_side': 1.0})
        self.p.update(json.loads(os.environ.get("STY_P", "{}")))
