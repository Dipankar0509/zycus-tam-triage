# Step-by-Step Guide to Run the Project

This guide provides the complete, copy-paste instructions to set up, run, and validate the **TAM Agentic Ticket Triage** project on both Windows and Linux/macOS.

---

## 📋 Prerequisites

* **Python:** 3.10, 3.11, 3.12, 3.13, or 3.14
* **Git:** Installed on your system
* **Terminal:** PowerShell, Command Prompt, or Bash

---

## 🚀 Step 1: Open Terminal & Navigate to Project

Open your terminal and change directory to the repository root:

```powershell
cd c:\Users\zycus\Downloads\Zycustask\starter-repo
```

---

## 🐍 Step 2: Set Up Virtual Environment (Recommended)

### On Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

*(If Python is not on your PATH, use the full path: `& "C:\Users\zycus\AppData\Local\Python\bin\python.exe" -m venv .venv`)*

### On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 📦 Step 3: Install Required Dependencies

Install the lightweight core libraries (`pydantic`, `python-dotenv`, `requests`):

```bash
pip install -r requirements.txt
```

---

## 🔑 Step 4: Configure Environment & API Key (Optional)

The system works **both offline and live**:

* **To run with Live Groq / Gemini LLM:**
  Copy `.env.example` to `.env`:
  ```powershell
  Copy-Item .env.example .env
  ```
  Open `.env` and add your API key:
  ```env
  GROQ_API_KEY=gsk_your_groq_api_key_here
  GROQ_MODEL=openai/gpt-oss-120b
  ```

* **To run Offline (Zero Cost / No API Key needed):**
  Simply leave `.env` empty or omitted. The system will automatically use the built-in heuristic reasoning engine.

---

## 🔍 Step 5: Verify Dataset Integrity

Run the dataset validation script to verify tickets, accounts, and knowledge-base markdown files:

```bash
python scripts/validate_data.py
```

**Expected Output:**
```text
============================================================
DATASET INTEGRITY VALIDATION
============================================================
[PASS] Tickets verified: 500 tickets loaded successfully.
[PASS] Accounts verified: 50 accounts loaded successfully.
[PASS] Knowledge Base verified: 9 markdown documents found across 4 modules.
[PASS] Review set verified: 10 review tickets configured.

[SUCCESS] ALL DATASET INTEGRITY CHECKS PASSED!
============================================================
```

---

## ⚡ Step 6: Run Triage on the 10 Review Tickets

Run the agent on the 10 review tickets configured in `data/review_set.txt`:

```bash
python run.py --set review
```

This will:
* Autonomously investigate each ticket (2–5 reasoning steps per ticket).
* Save individual JSON triage results to `outputs/<ticket_id>.json`.
* Write performance benchmarks and metadata to `outputs/run_log.jsonl`.

---

## 🎯 Step 7: (Optional) Run a Single Specific Ticket

You can test any ticket from `data/tickets.json` individually:

```bash
python run.py --ticket TKT-10042
```

---

## ✅ Step 8: Validate Outputs with Official Grader Check

Run the strict schema validation check required for assessment submission (must report **10/10 valid**):

```bash
python scripts/check_outputs.py
```

**Expected Output:**
```text
=================================================================
REVIEW-SET OUTPUT INTEGRITY & SCHEMA VALIDATION
=================================================================
Checking 10 review tickets against schema...

[01/10] TKT-10000: [PASS] Valid (Cat: Feature Request, Prio: P4, Steps: 5)
[02/10] TKT-10001: [PASS] Valid (Cat: Feature Request, Prio: P4, Steps: 2)
[03/10] TKT-10002: [PASS] Valid (Cat: Integration, Prio: P2, Steps: 4)
[04/10] TKT-10003: [PASS] Valid (Cat: How-To, Prio: P4, Steps: 4)
[05/10] TKT-10004: [PASS] Valid (Cat: Integration, Prio: P2, Steps: 3)
[06/10] TKT-10005: [PASS] Valid (Cat: Integration, Prio: P1, Steps: 5)
[07/10] TKT-10006: [PASS] Valid (Cat: Integration, Prio: P3, Steps: 4)
[08/10] TKT-10007: [PASS] Valid (Cat: How-To, Prio: P3, Steps: 5)
[09/10] TKT-10008: [PASS] Valid (Cat: Performance, Prio: P3, Steps: 3)
[10/10] TKT-10009: [PASS] Valid (Cat: How-To, Prio: P3, Steps: 5)
-----------------------------------------------------------------
Outputs Validation Result: 10/10 valid
Run Log (run_log.jsonl): [PASS] Present & populated
=================================================================

>>> RESULT: SUCCESS (10/10 VALID) - Ready for review! <<<
```

---

## 🖥️ Step 9: Launch the Visual TAM Triage Dashboard (Unique Feature!)

To visually inspect triaged tickets, customer health metrics, and the step-by-step reasoning trace in a clean web UI:

```bash
python serve_dashboard.py
```
*(Or double-click `dashboard.html` in your file explorer to open it directly in any browser!)*

---

## 📤 Step 10: Push to GitHub for Final Submission

1. Create a new repository on your GitHub account (e.g. `zycus-tam-ticket-triage`).
2. Run these commands from inside `starter-repo`:

```bash
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git branch -M main
git push -u origin main
```

*(Note: `.env` is automatically ignored by `.gitignore` so your secret API keys will never be pushed).*
