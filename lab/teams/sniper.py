"""Sniper sparring team (plan.md 26): reproduces how the top ladder teams
score on us - dribble everywhere (our engine with safe dribbling on the whole
pitch) and shoot readily, but only from inside 21 units."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v54 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "sniper"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32, "sd_xmin": -50.0, "sd_fwd": 0.02,
                       "shot_range": 21.0, "goal_bias": 0.0, "dom_on": 2.0})
        # Exploration hook: extra overrides from the environment.
        self.p.update(json.loads(os.environ.get("SK_P", "{}")))
