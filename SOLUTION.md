# SOLUTION.md — TAM Agentic Ticket Triage System

> **Candidate:** Dipankar Thorat · **Role:** AI Engineer — Product Support Intern · **Company:** Zycus

---

## 1. Architecture & Design Philosophy

Rather than a rigid pipeline, this system implements an **autonomous ReAct (Reasoning + Acting) loop** that mirrors how a senior TAM investigates tickets — dynamically choosing which tools to call based on ticket complexity and customer risk, not a pre-defined script.

```
╔══════════════════════════════════════════════════════╗
║           Incoming Support Ticket                    ║
╚══════════════════╤═══════════════════════════════════╝
                   │
                   ▼
╔══════════════════════════════════════════════════════╗
║       Autonomous Agent Loop  (tam_agent/agent.py)    ║  ◄─── Max 5 turns
║   Thought → Tool Call → Observe → Decide → Repeat   ║       (bounded cost)
╚═══╤══════════╤══════════╤══════════╤════════════════╝
    │          │          │          │
    ▼          ▼          ▼          ▼
┌──────────┐ ┌─────────┐ ┌────────────────┐ ┌──────────────────┐
│ resolve  │ │search_kb│ │get_ticket_hist.│ │check_support_    │
│ _account │ │ (BM25)  │ │(Dup. Detector) │ │policy (SLA tier) │
└──────────┘ └─────────┘ └────────────────┘ └──────────────────┘
    │          │          │          │
    └──────────┴──────────┴──────────┘
                   │   Aggregated Observations
                   ▼
╔══════════════════════════════════════════════════════╗
║           finalize_triage (Pydantic Schema)          ║
╚═══╤══════════════════════════════════════════════════╝
    │
    ├── outputs/TKT-XXXXX.json      (per-ticket artifact)
    └── outputs/run_log.jsonl       (full audit trail)
```

### Agent Tool Descriptions

| Tool | Purpose | When Called |
|------|---------|-------------|
| `resolve_account` | Fuzzy-match company name → account profile (tier, ARR, health, TAM) | **Always first** — needed for priority scoring |
| `search_kb` | BM25-ranked retrieval over 390+ KB chunks | When ticket describes technical symptoms |
| `get_ticket_history` | Duplicate detection + recurrence pattern analysis (90-day window) | On churn-risk or At-Risk accounts |
| `check_support_policy` | Pull SLA commitments by plan tier | Before finalizing P1/P2 escalations |
| `finalize_triage` | Emit strict Pydantic-validated JSON output | When sufficient context is gathered |

### Stopping Criteria
The agent stops when **either**:
- It has gathered account health + KB resolution + history context and calls `finalize_triage`, **or**
- It hits the **5-iteration safeguard** (bounded latency & cost guarantee)

---

## 2. Key Differentiators

### ✅ Resilient Account Resolution
Real-world ticket data contains blank `account_id`, legal name variations ("Inc", "Ltd", "Co"), and typos. The agent resolves accounts via **normalized fuzzy string matching** on company names rather than brittle ID lookups.

### ✅ Proactive Churn & Escalation Protection
The agent automatically:
- Detects `At Risk` / `Churning` health flags and overrides priority if under-triaged
- Alerts assigned TAM even for P4 tickets on enterprise At-Risk accounts
- Surfaces recurring ticket patterns (e.g., 3 P1s in 30 days) as churn risk signals

### ✅ Category Correction
When a customer mislabels a ticket (e.g., "Data Loss" for an SSO failure), the agent corrects the category using KB evidence and records the override in the `reasoning_trace`.

### ✅ Zero-Friction Execution
Works out-of-box with **no API keys required** via a built-in Offline Intelligent Engine, guaranteeing `10/10` schema validation passes even in air-gapped environments.

---

## 3. Evaluation Strategy

To promote this agent to production handling live customer tickets, we evaluate along **6 dimensions**:

| Dimension | Metric | Target |
|-----------|--------|--------|
| Account Resolution Accuracy | % tickets matched correctly despite dirty `account_id` data | > 99% |
| Priority/SLA Misclassification | Under-triage rate (true P1 → labeled P3+) | **Zero tolerance** |
| Retrieval Relevance | NDCG@3 / MRR on gold-labeled eval set | > 0.85 |
| TAM Notification Precision/Recall | Recall = 100% on high-ARR escalations, Precision = avoid noise | P = >90%, R = 100% |
| Hallucination & Schema Compliance | % outputs passing Pydantic strict validator | 100% |
| Customer Reply Quality | LLM-as-Judge + senior TAM spot-check (1–5 rubric) | Avg ≥ 4.0 |

---

## 4. Scalability Analysis (10× Production Load)

### Scenario: 30,000 tickets/month · 4,000 KB articles

**Cost**
- Current: ~4,000 tokens/ticket × 30,000 tickets = 120M tokens/month
- Using Gemini Flash ($0.10 / 1M tokens) → **under $15/month**
- Optimization: prompt caching, pre-filter obvious duplicates before LLM invocation

**Latency**
- Current: 1.5–3.0s/ticket sequential
- At 10×: Celery/BullMQ worker pool with 20 parallel workers → **30,000 tickets in < 1 hour**

**Retrieval Quality at 4,000 KB articles**

| Concern | Solution |
|---------|---------|
| Pure BM25 recall drops in large corpus | **Hybrid Search**: Dense embeddings (Vertex AI / `text-embedding-3-small`) + BM25 via Reciprocal Rank Fusion (RRF) |
| Synonym/paraphrase misses | Semantic vector search captures meaning, not just keywords |
| Irrelevant cross-product noise | Metadata pre-filtering by `product` and `product_area` before ranking |
| Top-10 quality | Cross-encoder re-ranking on top-10 BM25+vector candidates |

---

## 5. Current Limitations

1. **Semantic Deduplication Gap** — Current duplicate detection uses lexical subject overlap. Cross-ticket semantic similarity (e.g., same issue described differently) and log/image attachments are not yet compared.

2. **Cold-Start Accounts** — If a company has never appeared in `accounts.json` and `account_id` is blank, the system defaults to guest-tier routing (conservative fallback).

3. **No Direct Ticketing System Writeback** — Agent outputs structured JSON artifacts; it does not yet write comments, update ticket status, or dispatch alerts directly into Zendesk, Salesforce, or ServiceNow APIs.

4. **Single-turn KB retrieval** — Each KB search is one-shot BM25. A multi-step retrieval strategy (query reformulation, chain-of-thought search) would improve coverage for ambiguous technical descriptions.

---

## 6. How to Run

```bash
# 1. Setup virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

# 2. (Optional) Configure live LLM provider
cp .env.example .env
# Add GEMINI_API_KEY or GROQ_API_KEY in .env

# 3. Verify dataset integrity
python scripts/validate_data.py

# 4. Run triage agent on all 10 review tickets
python run.py --set review

# 5. Validate outputs — must show 10/10 valid
python scripts/check_outputs.py

# 6. Open the interactive dashboard
python serve_dashboard.py
# Or double-click dashboard.html
```
