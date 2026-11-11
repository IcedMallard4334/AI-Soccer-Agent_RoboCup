import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v12 import MyTeam as _Base


class MyTeam(_Base):
    name = "v12ref"

    def __init__(self):
        super().__init__()
        self.p["budget"] = 1.0
