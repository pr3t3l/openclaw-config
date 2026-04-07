#!/bin/bash
cd /home/robotin/.openclaw/workspace-meta-planner
exec python3 scripts/run_sdd_planner.py start "$*"
