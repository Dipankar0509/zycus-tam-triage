"""
scripts/validate_data.py - Confirms dataset integrity and file accessibility.
"""

import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def validate_dataset():
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    kb_dir = root / "knowledge-base"

    print("=" * 60)
    print("DATASET INTEGRITY VALIDATION")
    print("=" * 60)

    # 1. Check tickets.json
    tickets_path = data_dir / "tickets.json"
    if not tickets_path.exists():
        print(f"[FAIL] Missing tickets dataset at {tickets_path}")
        return False
    try:
        with open(tickets_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)
        assert isinstance(tickets, list) and len(tickets) > 0, "tickets.json must be a non-empty list"
        sample_ticket = tickets[0]
        for field in ["ticket_id", "subject", "body"]:
            assert field in sample_ticket, f"Missing required ticket field: {field}"
        print(f"[PASS] Tickets verified: {len(tickets):,} tickets loaded successfully.")
    except Exception as e:
        print(f"[FAIL] ERROR parsing tickets.json: {e}")
        return False

    # 2. Check accounts.json
    accounts_path = data_dir / "accounts.json"
    if not accounts_path.exists():
        print(f"[FAIL] Missing accounts dataset at {accounts_path}")
        return False
    try:
        with open(accounts_path, "r", encoding="utf-8") as f:
            accounts = json.load(f)
        assert isinstance(accounts, list) and len(accounts) > 0, "accounts.json must be a non-empty list"
        sample_acc = accounts[0]
        for field in ["account_id", "company", "plan_tier"]:
            assert field in sample_acc, f"Missing required account field: {field}"
        print(f"[PASS] Accounts verified: {len(accounts):,} accounts loaded successfully.")
    except Exception as e:
        print(f"[FAIL] ERROR parsing accounts.json: {e}")
        return False

    # 3. Check knowledge base
    if not kb_dir.exists():
        print(f"[FAIL] Missing knowledge-base directory at {kb_dir}")
        return False
    kb_files = list(kb_dir.rglob("*.md"))
    if not kb_files:
        print("[FAIL] No markdown articles found in knowledge-base/")
        return False
    print(f"[PASS] Knowledge Base verified: {len(kb_files)} markdown documents found across {len(set(f.parent.name for f in kb_files))} modules.")

    # 4. Check review_set.txt
    review_set_path = data_dir / "review_set.txt"
    if review_set_path.exists():
        with open(review_set_path, "r", encoding="utf-8") as f:
            review_ids = [line.strip() for line in f if line.strip()]
        print(f"[PASS] Review set verified: {len(review_ids)} review tickets configured.")
    else:
        print("[WARN] data/review_set.txt not found yet.")

    print("\n[SUCCESS] ALL DATASET INTEGRITY CHECKS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = validate_dataset()
    sys.exit(0 if success else 1)
