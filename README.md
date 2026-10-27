# Zycus TAM · Agentic Ticket Triage System

[![Validation](https://img.shields.io/badge/Schema%20Validation-10%2F10%20PASS-22c55e?style=flat-square&logo=checkmarx&logoColor=white)](scripts/check_outputs.py)
[![Architecture](https://img.shields.io/badge/Architecture-Autonomous%20ReAct%20Loop-6366f1?style=flat-square)](tam_agent/agent.py)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20Gemini%20%7C%20Offline-f59e0b?style=flat-square)](tam_agent/llm.py)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3b82f6?style=flat-square&logo=python&logoColor=white)](requirements.txt)
[![Dashboard](https://img.shields.io/badge/Dashboard-Glassmorphism%20UI-8b5cf6?style=flat-square)](dashboard.html)

> **An autonomous AI agent for Technical Account Management (TAM) triage** — built for the Zycus AI Engineer Assessment.

Instead of triaging tickets from raw text alone, this agent replicates how a **senior support engineer investigates**: it dynamically resolves the customer profile, evaluates account health and churn risk, retrieves matching troubleshooting playbooks from the Knowledge Base, detects duplicate submissions, verifies SLA policies, and drafts audit-ready customer replies and internal TAM notes.

---

## ✨ What Makes This Stand Out

| Feature | Description |
|---------|-------------|
| 🤖 **Truly Autonomous ReAct Loop** | The agent dynamically chooses which tools to invoke based on ticket complexity. Simple inquiries resolve in 2 steps; complex P1 outages on At-Risk enterprise accounts execute 4–5 investigative turns. |
| 🔍 **Resilient Account Resolution** | Handles dirty real-world data: blank `account_id`s, legal name variations (Inc / Ltd / Co), and typos — via normalized fuzzy company matching. |
| 📚 **BM25 Knowledge Base Engine** | Chunks and indexes 390+ markdown sections across products, troubleshooting guides, error code tables, and SLA policies. |
| ⚠️ **Proactive Churn Protection** | Auto-flags high-impact blockers on enterprise/at-risk accounts, overrides mislabeled priorities, and dispatches urgent TAM alerts. |
| 🖥️ **Glassmorphism Dashboard** | Premium interactive dark-mode web dashboard with frosted-glass UI, animated background, and priority filter tabs. |
| 🛡️ **Zero-Friction Execution** | Works out-of-box with **Groq LPU**, **Google Gemini**, or the built-in **Offline Intelligent Engine** — **10/10 validation guaranteed** with no API key required. |

---

## 🏛️ System Architecture

```
                        Incoming Support Ticket
                                  │
                                  ▼
             ┌────────────────────────────────────────┐
             │        Autonomous Agent Loop            │ ◄───┐
             │         (tam_agent/agent.py)            │     │
             └────────────────┬───────────────────────┘     │ Tool
                              │                             │ Observations
          ┌───────────────────┼──────────────────────────┐  │
          ▼                   ▼                          ▼  │
┌─────────────────┐  ┌──────────────────┐  ┌───────────────────────┐
│ resolve_account │  │    search_kb     │  │  get_ticket_history   │
│  (Fuzzy Match)  │  │ (BM25 Retrieval) │  │  (Duplicate Checker)  │
└─────────────────┘  └──────────────────┘  └───────────────────────┘
          │                   │                          │  │
          └───────────────────┼──────────────────────────┘  │
                              │                             │
                              ▼                             │
             ┌────────────────────────────────────────┐     │
             │         check_support_policy            │ ────┘
             │           (SLA by Tier)                 │
             └────────────────┬───────────────────────┘
                              │
                              ▼
             ┌────────────────────────────────────────┐
             │            finalize_triage              │
             │        (Strict Pydantic Schema)         │
             └──────────┬─────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
 outputs/<ticket_id>.json       outputs/run_log.jsonl
  (per-ticket artifact)           (full audit trail)
```

---

## 🚀 Quick Start

### 1 — Install Dependencies

```bash
cd starter-repo

# Create virtual environment (optional but recommended)
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

### 2 — Configure LLM Provider *(Optional)*

The system runs **both offline and live**. To use Groq or Gemini:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Option A: Groq (recommended — fastest)
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Option B: Google Gemini
GEMINI_API_KEY=your_gemini_key_here
```

> If omitted, the agent uses the built-in **Offline Intelligent Engine** — still produces 10/10 valid outputs.

### 3 — Validate Dataset Integrity

```bash
python scripts/validate_data.py
```
> Confirms 500 tickets, 50 accounts, and KB markdown articles are all intact.

### 4 — Run Triage on Review Set

```bash
python run.py --set review
```
> Autonomously triages tickets `TKT-10000` → `TKT-10009`, writes JSON to `outputs/`.

### 5 — Validate Outputs (Official Grader)

```bash
python scripts/check_outputs.py
```
> **Must report `10/10 valid`** to pass the assessment.

### 6 — Launch the Interactive Dashboard

```bash
python serve_dashboard.py
```
> Or simply double-click [`dashboard.html`](dashboard.html) in your browser.

---

## 📂 Repository Structure

```
starter-repo/
├── tam_agent/
│   ├── agent.py        # ★ Core autonomous ReAct agent — triage(ticket, ctx)
│   ├── schema.py       #   Strict Pydantic output schema & validator
│   ├── data.py         #   Account resolver, ticket history & duplicate detector
│   ├── kb.py           #   BM25 knowledge-base indexer & search engine
│   └── llm.py          #   Multi-provider client (Groq, Gemini, OpenAI, Offline)
│
├── data/
│   ├── tickets.json    # 500 synthetic enterprise support tickets
│   ├── accounts.json   # 50 synthetic customer account summaries
│   └── review_set.txt  # Official 10-ticket benchmark (TKT-10000…TKT-10009)
│
├── knowledge-base/     # Markdown documentation corpus (390+ indexed sections)
│   ├── products/       #   Product architecture, features & error code tables
│   ├── troubleshooting/#   Auth, SSO & integration playbooks
│   ├── billing/        #   Plans, seat limits & pricing tiers
│   └── onboarding/     #   Customer checklists & training paths
│
├── outputs/            # Triaged ticket artifacts & audit logs
│   ├── TKT-10000.json … TKT-10009.json
│   └── run_log.jsonl   #   Execution duration, steps taken & metadata
│
├── scripts/
│   ├── validate_data.py   # Confirms dataset integrity
│   └── check_outputs.py   # Official 10/10 schema compliance checker
│
├── dashboard.html      # Interactive glassmorphism web dashboard
├── serve_dashboard.py  # Zero-dependency local dashboard server
├── run.py              # CLI runner with rich terminal output
├── SOLUTION.md         # Technical writeup (Design · Eval · Scale · Limits)
├── RUN_GUIDE.md        # Step-by-step execution guide
├── requirements.txt    # Minimal core dependencies
└── .env.example        # Environment template
```

---

## 📑 Output Schema

Every triaged ticket produces a strictly validated JSON artifact:

```json
{
  "ticket_id":        "TKT-10005",
  "account_id":       "ACC-5396",
  "company":          "Cybertronics Ltd",
  "category":         "Integration",
  "priority":         "P1",
  "routing":          "Identity & Security Engineering",
  "escalation":       true,
  "tam_notification": true,
  "tam_name":         "Fatima Al-Rashid",
  "duplicate_status": false,
  "duplicate_ticket_id": null,
  "needs_clarification": false,
  "customer_reply":   "Dear Cybertronics Ltd Team, ...",
  "internal_note":    "CRITICAL P1: Cybertronics ($240k ARR, At Risk, 3 prior P1s)...",
  "reasoning_trace": [
    {
      "step": 1,
      "thought": "Must resolve account to evaluate ARR, tier, and health.",
      "tool_called": "resolve_account",
      "tool_args":   {"company": "Cybertronics Ltd"},
      "observation": "Resolved ACC-5396. Tier: Business, ARR: $240,000, Health: At Risk."
    }
  ]
}
```

---

## 📈 Production Readiness Summary

| Dimension | Current | At 10× (30k tickets/mo) |
|-----------|---------|--------------------------|
| **Cost** | ~$0.05/1k tickets | **< $15/month** (Gemini Flash) |
| **Latency** | 1.5–3.0s/ticket | < 1 hour with 20 async workers |
| **KB Scale** | 390+ sections, BM25 | Hybrid Search (Dense + BM25 + RRF) |
| **Schema Compliance** | 10/10 Pydantic | Enforced in pre-write validation |

For full architectural details, evaluation strategy, and limitations → see [**`SOLUTION.md`**](SOLUTION.md).
