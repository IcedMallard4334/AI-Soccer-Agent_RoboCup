"""Self-play proxy of the top ladder teams' style (plan.md 10.1): our own
engine (v54) keeping the ball at its feet everywhere (safe dribble with no
half-way restriction), shooting only from close in."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v54 import MyTeam as _Base  # noqa: E402


class MyTeam(_Base):
    name = "selfkeep"

    def __init__(self):
        super().__init__()
        self.p.update({"budget": 1.0, "max_evals": 32, "sd_xmin": -50.0, "sd_fwd": 0.02,
                       "shot_range": 26.0, "dom_on": 2.0})
        # Exploration hook: extra overrides from the environment.
        self.p.update(json.loads(os.environ.get("SK_P", "{}")))
