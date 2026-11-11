"""Style opponent (plan.md 22): our own engine (v61) with a different
personality - shoots from anywhere up to 45 units, readily."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v61 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sty_shooter"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32})
        self.p.update({'shot_range': 45.0, 'goal_bias': 0.0, 'shot_n1': 7, 'dom_mode': {'goal_bias': 0.0, 'shot_range': 45.0, 'box_on': 1}})
        self.p.update(json.loads(os.environ.get("STY_P", "{}")))
