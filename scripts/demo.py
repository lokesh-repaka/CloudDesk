#!/usr/bin/env python3
"""CloudDesk Terminal Demo Runner Script (P11-5).

Demonstrates:
- CD-1002: Human-in-the-loop approval gate on consequential operations (`create_refund_request`).
- CD-1005: Deterministic policy escalation for security incidents.

Usage:
    python scripts/demo.py
    python scripts/demo.py --ticket CD-1005
    python scripts/demo.py --all
    make demo
    make demo TICKET=CD-1005
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.demo import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
