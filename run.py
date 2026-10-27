"""
run.py  ─  CLI runner for TAM Agentic Ticket Triage.
Executes the autonomous agent and writes results to:
  outputs/<ticket_id>.json   (per-ticket structured artifact)
  outputs/run_log.jsonl      (full execution audit trail)
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── UTF-8 on Windows consoles ─────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tam_agent.agent import AgentContext, triage

# ── ANSI colour helpers (auto-disable if not supported) ───────────────
def _supports_colour():
    import os
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_colour()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def bold(t):       return _c("1",    t)
def dim(t):        return _c("2",    t)
def blue(t):       return _c("94",   t)
def cyan(t):       return _c("96",   t)
def green(t):      return _c("92",   t)
def yellow(t):     return _c("93",   t)
def red(t):        return _c("91",   t)
def magenta(t):    return _c("95",   t)
def grey(t):       return _c("90",   t)
def white_bold(t): return _c("1;97", t)

# ── Priority colouring ────────────────────────────────────────────────
def prio_color(p):
    return { "P1": red, "P2": yellow, "P3": cyan, "P4": grey }.get(p, str)

# ── Decorative helpers ────────────────────────────────────────────────
W = 70  # terminal width

def hr(char="─", color=dim):
    print(color(char * W))

def banner():
    hr("═")
    print(bold(blue(f"  {'ZYCUS  ·  TAM  AGENTIC  TRIAGE  RUNNER':^{W-2}}")))
    print(dim(f"  {'Autonomous ReAct Agent  ·  Powered by BM25 + LLM Reasoning':^{W-2}}"))
    hr("═")

def section(title: str, icon: str = ""):
    print()
    print(f"  {cyan('▸')} {bold(title)}")

def tick_row(idx, total, t_id, company, prio, cat, steps, elapsed, status):
    p_fn = prio_color(prio)
    status_str = green("✔ DONE") if status == "ok" else red("✘ FAILED")
    prio_str   = p_fn(f"[{prio}]")
    elapsed_str = grey(f"{elapsed:.2f}s")

    print(
        f"  {grey(f'{idx:02d}/{total:02d}')}  "
        f"{blue(t_id):<18}  "
        f"{prio_str:<14}  "
        f"{white_bold(company):<28}  "
        f"{cyan(cat):<20}  "
        f"{grey(f'{steps}steps'):<8}  "
        f"{elapsed_str:<8}  "
        f"{status_str}"
    )

def summary_table(results):
    hr()
    section("Run Summary", "📊")
    hr()

    counts   = { "P1": 0, "P2": 0, "P3": 0, "P4": 0 }
    esc_count = 0
    tam_count = 0
    total_s   = 0.0
    errors    = 0

    for r in results:
        p = r.get("priority", "?")
        if p in counts:
            counts[p] += 1
        if r.get("escalation"):
            esc_count += 1
        if r.get("tam_notification"):
            tam_count += 1
        total_s += r.get("duration_seconds", 0)
        if r.get("status") == "ERROR":
            errors += 1

    ok = len(results) - errors
    print(f"  {'Tickets processed':.<36} {white_bold(str(ok + errors))}")
    print(f"  {'Successful':.<36} {green(str(ok))}")
    print(f"  {'Failed':.<36} {(red if errors else grey)(str(errors))}")
    print(f"  {'Total elapsed':.<36} {yellow(f'{total_s:.2f}s')}  "
          f"{grey(f'(avg {total_s/max(len(results),1):.2f}s/ticket)')}")

    print()
    print(f"  {'P1 (Critical)':.<36} {red(str(counts['P1']))}")
    print(f"  {'P2 (High)':.<36} {yellow(str(counts['P2']))}")
    print(f"  {'P3 (Medium)':.<36} {cyan(str(counts['P3']))}")
    print(f"  {'P4 (Low)':.<36} {grey(str(counts['P4']))}")
    print()
    print(f"  {'Escalations raised':.<36} {(red if esc_count else grey)(str(esc_count))}")
    print(f"  {'TAM notifications sent':.<36} {(yellow if tam_count else grey)(str(tam_count))}")
    hr()


def run_agent(args):
    root        = Path(__file__).parent
    data_dir    = root / "data"
    kb_dir      = root / "knowledge-base"
    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    banner()
    print()

    # ── Init context ──────────────────────────────────────────────────
    print(f"  {magenta('⬡')} Initializing Agent Context & Knowledge Base…")
    ctx = AgentContext(str(data_dir), str(kb_dir))

    tickets_n  = len(ctx.data_loader.tickets)
    accounts_n = len(ctx.data_loader.accounts)
    chunks_n   = len(ctx.kb.chunks)
    llm_mode   = "Live LLM ✦" if ctx.llm.has_live_llm else "Offline Intelligent Engine"

    print(f"    {grey('Tickets loaded:'):<30} {cyan(str(tickets_n))}")
    print(f"    {grey('Accounts loaded:'):<30} {cyan(str(accounts_n))}")
    print(f"    {grey('KB sections indexed:'):<30} {cyan(str(chunks_n))}")
    print(f"    {grey('LLM provider:'):<30} {green(llm_mode)}")
    print(f"    {grey('Start time:'):<30} {grey(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))}")

    # ── Determine tickets ─────────────────────────────────────────────
    target_ids = []
    if args.ticket:
        target_ids = [args.ticket.strip()]
    elif args.set == "review":
        review_path = data_dir / "review_set.txt"
        if not review_path.exists():
            print(red(f"\n  [ERROR] review_set.txt not found at {review_path}\n"))
            sys.exit(1)
        with open(review_path, "r", encoding="utf-8") as f:
            target_ids = [line.strip() for line in f if line.strip()]
    elif args.all:
        target_ids = [t["ticket_id"] for t in ctx.data_loader.tickets]
    else:
        review_path = data_dir / "review_set.txt"
        if review_path.exists():
            with open(review_path, "r", encoding="utf-8") as f:
                target_ids = [line.strip() for line in f if line.strip()]
        else:
            target_ids = [t["ticket_id"] for t in ctx.data_loader.tickets[:10]]

    if args.limit:
        target_ids = target_ids[: args.limit]

    print()
    print(f"  {magenta('⬡')} Processing {bold(str(len(target_ids)))} tickets …")
    hr()

    # Column headers
    print(
        f"  {grey('##/##')}  "
        f"{grey('Ticket ID'):<18}  "
        f"{grey('Priority'):<14}  "
        f"{grey('Company'):<28}  "
        f"{grey('Category'):<20}  "
        f"{grey('Steps'):<8}  "
        f"{grey('Time'):<8}  "
        f"{grey('Status')}"
    )
    hr()

    # ── Main triage loop ──────────────────────────────────────────────
    run_log_path = outputs_dir / "run_log.jsonl"
    results      = []

    for idx, t_id in enumerate(target_ids, 1):
        ticket = ctx.data_loader.tickets_by_id.get(t_id)
        if not ticket:
            print(f"  {red('✘')} {t_id} — NOT FOUND in tickets.json, skipping.")
            continue

        t0 = time.time()
        try:
            output  = triage(ticket, ctx)
            elapsed = time.time() - t0

            # Save per-ticket JSON
            out_file = outputs_dir / f"{t_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            prio     = output.get("priority", "?")
            cat      = output.get("category", "?")
            company  = output.get("company", ticket.get("company", "?"))
            steps    = len(output.get("reasoning_trace", []))

            tick_row(idx, len(target_ids), t_id, company, prio, cat, steps, elapsed, "ok")

            log_entry = {
                "ticket_id":        t_id,
                "timestamp":        datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(elapsed, 3),
                "resolved_account": output.get("account_id"),
                "company":          company,
                "category":         cat,
                "priority":         prio,
                "escalation":       output.get("escalation"),
                "tam_notification": output.get("tam_notification"),
                "steps_taken":      steps,
                "status":           "SUCCESS",
            }
            results.append({**log_entry, "priority": prio, "escalation": output.get("escalation"), "tam_notification": output.get("tam_notification")})

        except Exception as e:
            elapsed = time.time() - t0
            tick_row(idx, len(target_ids), t_id,
                     ticket.get("company", "?"), "??", "??", 0, elapsed, "err")
            print(f"    {red('→')} {red(str(e))}")
            log_entry = {
                "ticket_id":        t_id,
                "timestamp":        datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(elapsed, 3),
                "status":           "ERROR",
                "error":            str(e),
            }
            results.append({"priority": "??", "escalation": False, "tam_notification": False,
                             "duration_seconds": elapsed, "status": "ERROR"})

        with open(run_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    # ── Summary ───────────────────────────────────────────────────────
    summary_table(results)

    ok_count = sum(1 for r in results if r.get("status") != "ERROR")
    print(f"  {magenta('⬡')} Output artifacts  →  {blue(str(outputs_dir))}")
    print(f"  {magenta('⬡')} Audit log         →  {blue(str(run_log_path))}")
    print()

    if ok_count == len(target_ids):
        print(f"  {green('✔')} {green(bold(f'All {ok_count} tickets triaged successfully.'))}")
    else:
        print(f"  {yellow('⚠')} {yellow(f'{ok_count}/{len(target_ids)} tickets succeeded.')}")

    print()
    print(f"  {grey('Next step:')} run {cyan('python scripts/check_outputs.py')} to validate schema compliance.")
    hr("═")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="TAM Agentic Ticket Triage Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python run.py --set review\n"
               "  python run.py --ticket TKT-10005\n"
               "  python run.py --all --limit 20",
    )
    parser.add_argument("--set",    choices=["review"], default="review",
                        help="Ticket set to run (default: review)")
    parser.add_argument("--ticket", type=str,
                        help="Single ticket ID to triage (e.g. TKT-10005)")
    parser.add_argument("--all",    action="store_true",
                        help="Run triage on all 500 tickets")
    parser.add_argument("--limit",  type=int,
                        help="Limit number of tickets to process")
    args = parser.parse_args()
    run_agent(args)


if __name__ == "__main__":
    main()
