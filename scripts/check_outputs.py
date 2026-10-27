"""
scripts/check_outputs.py - Confirms review-set outputs are valid according to schema.
Must report 10/10 valid for submission eligibility.
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

# Add parent to path for tam_agent import
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from tam_agent.schema import TriageResult, validate_triage_dict


def check_outputs():
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    review_path = data_dir / "review_set.txt"

    print("=" * 65)
    print("REVIEW-SET OUTPUT INTEGRITY & SCHEMA VALIDATION")
    print("=" * 65)

    if not review_path.exists():
        print(f"[ERROR] Missing {review_path}")
        return False

    with open(review_path, "r", encoding="utf-8") as f:
        review_ids = [line.strip() for line in f if line.strip()]

    total = len(review_ids)
    if total == 0:
        print("[ERROR] review_set.txt contains no ticket IDs!")
        return False

    if not outputs_dir.exists():
        print(f"[ERROR] Outputs directory {outputs_dir} does not exist!")
        print("Run `python run.py --set review` first to generate outputs.")
        return False

    valid_count = 0
    errors = []

    print(f"Checking {total} review tickets against schema...\n")

    for idx, t_id in enumerate(review_ids, 1):
        out_file = outputs_dir / f"{t_id}.json"
        if not out_file.exists():
            print(f"[{idx:02d}/{total:02d}] {t_id}: [FAIL] Output file missing: {out_file.name}")
            errors.append(f"{t_id}: Missing output file")
            continue

        try:
            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate schema
            is_valid, err_msg = validate_triage_dict(data)
            if not is_valid:
                print(f"[{idx:02d}/{total:02d}] {t_id}: [FAIL] Schema validation error: {err_msg}")
                errors.append(f"{t_id}: {err_msg}")
                continue

            # Additional checks for quality
            trace = data.get("reasoning_trace", [])
            reply = data.get("customer_reply", "")
            note = data.get("internal_note", "")

            if not trace or len(trace) < 1:
                print(f"[{idx:02d}/{total:02d}] {t_id}: [FAIL] reasoning_trace is empty!")
                errors.append(f"{t_id}: Empty reasoning trace")
                continue

            if len(reply.strip()) < 20 or len(note.strip()) < 20:
                print(f"[{idx:02d}/{total:02d}] {t_id}: [FAIL] customer_reply or internal_note too brief!")
                errors.append(f"{t_id}: Replies/notes too short")
                continue

            valid_count += 1
            print(f"[{idx:02d}/{total:02d}] {t_id}: [PASS] Valid (Cat: {data.get('category')}, Prio: {data.get('priority')}, Steps: {len(trace)})")

        except Exception as e:
            print(f"[{idx:02d}/{total:02d}] {t_id}: [FAIL] JSON load error: {e}")
            errors.append(f"{t_id}: {e}")

    # Check run_log.jsonl
    run_log = outputs_dir / "run_log.jsonl"
    has_log = run_log.exists() and run_log.stat().st_size > 0

    print("-" * 65)
    print(f"Outputs Validation Result: {valid_count}/{total} valid")
    print(f"Run Log (run_log.jsonl): {'[PASS] Present & populated' if has_log else '[FAIL] Missing or empty'}")
    print("=" * 65)

    if valid_count == total and has_log:
        print(f"\n>>> RESULT: SUCCESS ({valid_count}/{total} VALID) - Ready for review! <<<\n")
        return True
    else:
        print(f"\n>>> RESULT: FAILED ({valid_count}/{total} valid) <<<\n")
        return False


if __name__ == "__main__":
    passed = check_outputs()
    sys.exit(0 if passed else 1)
