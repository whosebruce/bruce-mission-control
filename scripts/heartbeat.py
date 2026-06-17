#!/usr/bin/env python3
"""
Bruce Mission Control — agent heartbeat client

Each bot (Mira / Apollo / Otto / Jade) calls this script on a schedule.
It POSTs to /api/agents/state with the bot's current status.

Usage:
  heartbeat.py --agent mira     --status working --task "Drafting Mira digest"
  heartbeat.py --agent jade     --status online  --task "Frontier lab scan"
  heartbeat.py --agent otto     --status idle
  heartbeat.py --agent apollo   --status error   --task "Higgsfield 429s"

Environment:
  MISSION_CONTROL_URL    (default: http://127.0.0.1:3000)
  MISSION_CONTROL_SECRET (required — the INTERNAL_API_SECRET from .env)

Cron example (every 5 min, per agent):
  */5 * * * * /usr/local/bin/heartbeat.py --agent jade --status working --task "Auto: scanning frontier labs"
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def main():
    p = argparse.ArgumentParser(description="Bruce Mission Control heartbeat client")
    p.add_argument("--agent", required=True, choices=["mira", "apollo", "otto", "jade"],
                   help="Which bot is heartbeating")
    p.add_argument("--status", default="online",
                   choices=["online", "idle", "working", "offline", "error"],
                   help="Current status")
    p.add_argument("--task", default=None, help="What the agent is doing right now (optional)")
    p.add_argument("--cost", type=float, default=None,
                   help="Cumulative session cost in USD (optional, increments on server)")
    p.add_argument("--completed", type=int, default=None,
                   help="Total tasks completed (optional)")
    p.add_argument("--url", default=os.environ.get("MISSION_CONTROL_URL", "http://127.0.0.1:3000"),
                   help="Mission Control base URL")
    args = p.parse_args()

    secret = os.environ.get("MISSION_CONTROL_SECRET")
    if not secret:
        print("ERROR: MISSION_CONTROL_SECRET env var not set", file=sys.stderr)
        sys.exit(2)

    AGENT_META = {
        "mira":   {"name": "Mira",   "emoji": "🪞", "role": "Knowledge / Orchestration"},
        "apollo": {"name": "Apollo", "emoji": "🎨", "role": "Creative / Design"},
        "otto":   {"name": "Otto",   "emoji": "🔧", "role": "Ops / Home"},
        "jade":   {"name": "Jade",   "emoji": "🔭", "role": "Research / Frontier Intel"},
    }
    meta = AGENT_META[args.agent]

    payload = {
        "id": args.agent,
        "name": meta["name"],
        "emoji": meta["emoji"],
        "role": meta["role"],
        "status": args.status,
        "currentTask": args.task,
        "lastActive": datetime.now(timezone.utc).isoformat(),
    }
    if args.cost is not None:
        payload["totalCost"] = args.cost
    if args.completed is not None:
        payload["tasksCompleted"] = args.completed

    req = urllib.request.Request(
        f"{args.url}/api/agents/state",
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(f"[{args.agent}] {resp.status} {body}")
    except urllib.error.HTTPError as e:
        print(f"[{args.agent}] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[{args.agent}] connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()