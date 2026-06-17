#!/usr/bin/env python3
"""
Bruce Mission Control — heartbeat daemon

Watches the four Hermes gateway services (mira, apollo, otto, jade), reads
their live state (active/inactive + journal tail for current task), and POSTs
a heartbeat to /api/agents/state every HEARTBEAT_INTERVAL seconds.

This sits *outside* Hermes — it only observes via systemctl + journalctl — so
Hermes updates won't break it. Each gateway's actual state is the source of
truth, not a guessed cron trigger.

Per-bot heartbeat shape:
  id           = mira | apollo | otto | jade
  name         = bot display name
  emoji        = bot emoji
  role         = bot role
  status       = online | working | idle | offline | error
  currentTask  = the most recent meaningful journal line (or null)
  lastActive   = ISO timestamp
  tasksCompleted = rolling counter (incremented by status==working transitions)
  totalCost    = 0 (we don't track cost from outside Hermes; left for future)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------- Config (env-overridable) ----------
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "300"))  # 5 min default
MISSION_CONTROL_URL = os.environ.get("MISSION_CONTROL_URL", "http://127.0.0.1:8080")
SECRET = os.environ.get("MISSION_CONTROL_SECRET")
if not SECRET:
    # Fall back to the .env file in the project root if env not set
    env_path = "/home/bruce/.hermes/projects/bruce-mission-control/.env"
    if os.path.isfile(env_path):
        for line in open(env_path):
            if line.startswith("INTERNAL_API_SECRET="):
                SECRET = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not SECRET:
    print("FATAL: MISSION_CONTROL_SECRET not set and .env not readable", file=sys.stderr)
    sys.exit(2)

# ---------- Bot roster ----------
BOTS = [
    # id,     display,  emoji, role,                          service-name
    ("mira",   "Mira",   "🪞", "Knowledge / Orchestration",  "hermes-gateway.service"),
    ("apollo", "Apollo", "🎨", "Creative / Design",          "hermes-gateway-apollo.service"),
    ("otto",   "Otto",   "🔧", "Ops / Home",                 "hermes-gateway-otto.service"),
    ("jade",   "Jade",   "🔭", "Research / Frontier Intel",  "hermes-gateway-jade.service"),
]

# Log lines that are routine and shouldn't count as "current task"
ROUTINE_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"DEBUG|TRACE|heartbeat", re.IGNORECASE),
    re.compile(r"^\[gateway\]", re.IGNORECASE),
    re.compile(r"scheduler tick", re.IGNORECASE),
]


def is_routine(line: str) -> bool:
    return any(p.search(line) for p in ROUTINE_PATTERNS)


def get_service_status(svc: str) -> tuple[str, str | None, str | None]:
    """
    Return (status, current_task, error_detail)
      status:        "working" | "online" | "idle" | "offline" | "error"
      current_task:  most recent meaningful journal line, or None
      error_detail:  if status is "error", a short reason
    """
    # 1. Service state
    r = subprocess.run(
        ["systemctl", "--user", "is-active", svc],
        capture_output=True, text=True, timeout=5
    )
    active = r.stdout.strip()

    if active == "active":
        # 2. Recent journal — tail the last 50 lines, find the most recent non-routine
        rj = subprocess.run(
            ["journalctl", "--user", "-u", svc, "-n", "50", "--no-pager", "-q"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l for l in rj.stdout.splitlines() if l.strip()]
        # Reverse-find the first non-routine line
        task = None
        for line in reversed(lines):
            # journalctl prefix is "Jun 17 21:00:00 openclaw (gateway)[1234]: actual log"
            # Strip the syslog header to inspect just the message
            m = re.match(r"^[A-Z][a-z]{2} +\d+ +\d{2}:\d{2}:\d{2} \S+ \S+:\s*(.*)$", line)
            msg = m.group(1) if m else line
            if not is_routine(msg):
                # Trim and bound length
                task = msg.strip()[:140]
                break

        # 3. Working vs idle: if there's been log activity in the last 5 min
        #    we say "working", else "idle".
        try:
            rj2 = subprocess.run(
                ["journalctl", "--user", "-u", svc, "-n", "1", "--no-pager",
                 "-q", "--since", "5 minutes ago"],
                capture_output=True, text=True, timeout=5
            )
            recent = bool(rj2.stdout.strip())
        except Exception:
            recent = False
        status = "working" if recent else "idle"
        return status, task, None

    if active in ("inactive", "failed", "deactivating"):
        # Show the last failure line if any
        rj = subprocess.run(
            ["journalctl", "--user", "-u", svc, "-n", "20", "--no-pager",
             "-q", "-p", "err"],
            capture_output=True, text=True, timeout=5
        )
        err_lines = [l for l in rj.stdout.splitlines() if l.strip()]
        err = err_lines[-1][:200] if err_lines else f"service {active}"
        return ("error" if active == "failed" else "offline"), None, err

    return "offline", None, f"unknown state: {active}"


def post_heartbeat(bot_id: str, name: str, emoji: str, role: str,
                   status: str, task: str | None) -> bool:
    payload = {
        "id": bot_id,
        "name": name,
        "emoji": emoji,
        "role": role,
        "status": status,
        "currentTask": task,
        "lastActive": datetime.now(timezone.utc).isoformat(),
    }
    req = urllib.request.Request(
        f"{MISSION_CONTROL_URL}/api/agents/state",
        method="POST",
        headers={
            "Authorization": f"Bearer {SECRET}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(f"  [{bot_id:8s}] HTTP {resp.status} status={status:8s} task={(task or '-')[:60]}")
            return resp.status < 400
    except urllib.error.HTTPError as e:
        print(f"  [{bot_id:8s}] HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}",
              file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"  [{bot_id:8s}] conn: {e.reason}", file=sys.stderr)
        return False


def main() -> None:
    print(f"[heartbeat-daemon] starting, interval={HEARTBEAT_INTERVAL}s, target={MISSION_CONTROL_URL}")
    while True:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"\n[heartbeat-daemon] tick {ts}")
        for bot_id, name, emoji, role, svc in BOTS:
            try:
                status, task, err = get_service_status(svc)
            except Exception as e:
                print(f"  [{bot_id:8s}] check failed: {e}", file=sys.stderr)
                continue
            post_heartbeat(bot_id, name, emoji, role, status, task)
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[heartbeat-daemon] stopped")
        sys.exit(0)
