#!/usr/bin/env bash
# Full gauntlet for a release candidate: every old version, the archetypes and
# the strongest baselines; first pure quality (no deadline pressure), then the
# real 20 ms deadline with 4 parallel workers.
#   bash lab/final_check.sh lab/teams/vNN.py lab/teams/vNNref.py [seeds]
set -e
cd "$(dirname "$0")/.."
TEAM="$1"; REF="$2"; SEEDS="${3:-1000..1019}"
OLD="lab/teams/v1.py lab/teams/v2.py lab/teams/v3.py lab/teams/v4.py lab/teams/v5.py lab/teams/v6ref.py \
lab/teams/v7ref.py lab/teams/v8ref.py lab/teams/v9ref.py lab/teams/v11ref.py lab/teams/v13ref.py \
lab/teams/v14ref.py lab/teams/v16ref.py lab/teams/v17ref.py lab/teams/v18ref.py lab/teams/v19ref.py lab/teams/v20ref.py"
echo "=== quality: $REF (no deadline pressure)"
py -3 lab/bench.py "$REF" --vs $OLD lab/teams/bus.py lab/teams/rusher.py elite tactical --seeds "$SEEDS" --workers 8 --timeout 1000
echo "=== real conditions: $TEAM (20 ms deadline, 4 workers)"
py -3 lab/bench.py "$TEAM" --vs lab/teams/v1.py lab/teams/v3.py lab/teams/v9.py lab/teams/v14.py lab/teams/v18.py lab/teams/v20.py lab/teams/bus.py elite --seeds 1000..1009 --workers 4
