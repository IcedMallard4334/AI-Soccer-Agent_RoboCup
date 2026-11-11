"""Pooled match statistics for team A vs team B.  py -3 lab/stats.py A B 1000..1009"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bootstrap
bootstrap.ensure_engine()
from soccer.runner import evaluate

KEYS = ['goals_per_match', 'possession_fraction', 'control_fraction', 'territory_fraction',
        'shots_per_match', 'shots_blocked_per_match', 'passes_attempted_per_match',
        'pass_completion', 'mean_pass_distance', 'passes_intercepted_per_match',
        'dribbles_per_match', 'mean_dribble_distance', 'turnovers_per_match',
        'tackles_attempted_per_match', 'tackle_success']

if __name__ == '__main__':
    a, b = sys.argv[1], sys.argv[2]
    s0, s1 = sys.argv[3].split('..')
    r = evaluate(a, b, seeds=range(int(s0), int(s1) + 1), workers=8, per_decision_timeout_ms=1000)
    s = r['summary']
    print('%s vs %s: %d-%d-%d goals %s' % (os.path.basename(a), os.path.basename(b),
          s['team_a_wins'], s['draws'], s['team_b_wins'], s['goals']))
    for k in KEYS:
        print('  %-30s %8.3f %8.3f' % (k, s['team_stats'][0].get(k, 0), s['team_stats'][1].get(k, 0)))
