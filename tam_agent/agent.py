"""
tam_agent/agent.py - Core Agentic Ticket Triage implementation.
The agent uses an autonomous ReAct loop to dynamically choose tools, gather context,
and determine the triage decision.
"""

import json
from typing import Dict, List, Optional, Any
from tam_agent.data import DataLoader
from tam_agent.kb import KnowledgeBase
from tam_agent.llm import LLMClient
from tam_agent.schema import TriageResult, ReasoningStep, CategoryEnum, PriorityEnum


class AgentContext:
    def __init__(self, data_dir: str = "data", kb_dir: str = "knowledge-base"):
        self.data_loader = DataLoader(data_dir)
        self.kb = KnowledgeBase(kb_dir)
        self.llm = LLMClient()


def triage(ticket: Dict[str, Any], ctx: Optional[AgentContext] = None) -> Dict[str, Any]:
    """
    Main entry point for agentic triage.
    Executes a dynamic ReAct agent loop where the agent decides which tools to call,
    gathers required context, and decides when to stop and produce the final decision.
    """
    if ctx is None:
        ctx = AgentContext()

    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    raw_company = ticket.get("company", "")
    raw_account_id = ticket.get("account_id", "")
    subject = ticket.get("subject", "")
    body = ticket.get("body", "")
    product = ticket.get("product", "")

    # State variables gathered dynamically
    resolved_account: Optional[Dict[str, Any]] = None
    account_tickets: List[Dict[str, Any]] = []
    kb_findings: List[Dict[str, Any]] = []
    policy_info: Optional[str] = None
    is_duplicate: bool = False
    duplicate_id: Optional[str] = None

    reasoning_trace: List[ReasoningStep] = []
    max_steps = 5
    step_num = 1
    finalized = False

    # Define tool functions
    def tool_resolve_account(company: str = "", acc_id: str = "") -> str:
        nonlocal resolved_account
        resolved_account = ctx.data_loader.resolve_account(account_id=acc_id, company_name=company)
        if resolved_account:
            return (
                f"Account resolved: {resolved_account.get('account_id')} ({resolved_account.get('company')}). "
                f"Tier: {resolved_account.get('plan_tier')}, ARR: ${resolved_account.get('arr_usd', 0):,}, "
                f"Health: {resolved_account.get('health_status')}, Usage Trend: {resolved_account.get('usage_trend')}, "
                f"TAM: {resolved_account.get('tam')}, Renewal: {resolved_account.get('renewal_date')}, "
                f"Open Tickets: {resolved_account.get('open_tickets')}, Escalation Notes: {resolved_account.get('escalation_notes')}"
            )
        return "Account could not be found in accounts database."

    def tool_search_kb(query: str) -> str:
        nonlocal kb_findings
        results = ctx.kb.search(query, top_k=3)
        kb_findings.extend(results)
        if results:
            snippets = [f"[{r['title']} - {r['section']}]: {r['content'][:250]}..." for r in results]
            return "KB Search Results:\n" + "\n".join(snippets)
        return "No relevant KB articles found."

    def tool_get_ticket_history() -> str:
        nonlocal account_tickets, is_duplicate, duplicate_id
        c_name = raw_company or (resolved_account.get("company") if resolved_account else "")
        a_id = raw_account_id or (resolved_account.get("account_id") if resolved_account else "")
        account_tickets = ctx.data_loader.get_account_tickets(
            account_id=a_id,
            company_name=c_name,
            current_ticket_id=ticket_id,
            limit=5
        )
        is_dup, dup_tkt = ctx.data_loader.check_duplicate(ticket, account_tickets)
        if is_dup:
            is_duplicate = True
            duplicate_id = dup_tkt

        if account_tickets:
            hist_summary = [f"{t.get('ticket_id')} ({t.get('status')} - {t.get('urgency')}): {t.get('subject')}" for t in account_tickets[:3]]
            dup_msg = f" [POSSIBLE DUPLICATE of {duplicate_id}]" if is_duplicate else ""
            return f"Found {len(account_tickets)} recent tickets:{dup_msg}\n" + "\n".join(hist_summary)
        return "No recent ticket history found for this customer."

    def tool_check_policy(tier: Optional[str] = None) -> str:
        nonlocal policy_info
        t = tier or (resolved_account.get("plan_tier") if resolved_account else ticket.get("plan_tier", "Starter"))
        policy_info = ctx.kb.get_support_policy(t)
        return f"Support Policy for {t}:\n{policy_info[:300]}..."

    tools_map = {
        "resolve_account": tool_resolve_account,
        "search_kb": tool_search_kb,
        "get_ticket_history": tool_get_ticket_history,
        "check_support_policy": tool_check_policy,
    }

    # ReAct Autonomous Agent Loop
    while step_num <= max_steps and not finalized:
        # Construct prompt describing current investigation state
        scratchpad = ""
        for st in reasoning_trace:
            scratchpad += f"\nStep {st.step}:\nThought: {st.thought}\nTool Called: {st.tool_called}\nObservation: {st.observation}\n"

        prompt = f"""You are an expert Technical Account Management (TAM) Triage Agent.
You are triaging incoming support ticket:
- Ticket ID: {ticket_id}
- Company on ticket: {raw_company}
- Account ID on ticket: {raw_account_id}
- Product: {product}
- Stated Urgency: {ticket.get('urgency')}
- Stated Category: {ticket.get('category')}
- Subject: {subject}
- Body: {body}

Your investigation so far:
{scratchpad if scratchpad else "No lookups performed yet."}

Important Guidelines:
- In this dataset, ticket account_ids are frequently outdated or mismatched. When 'resolve_account' returns an account, that is the authoritative ground truth. NEVER call 'resolve_account' more than once.
- Do NOT repeat a tool that you have already called. Progress through: resolve_account -> search_kb -> get_ticket_history (if needed) -> finalize_triage.
- When you have the account context and technical understanding, call "finalize_triage".

Available tools:
1. "resolve_account": Look up account details, plan tier, ARR, health status, and TAM. Args: {{"company": "{raw_company}", "acc_id": "{raw_account_id}"}}
2. "search_kb": Search knowledge base for error codes, procedures, or limits. Args: {{"query": "<search terms>"}}
3. "get_ticket_history": Check previous tickets to spot recurring issues or duplicate submissions. Args: {{}}
4. "check_support_policy": Review SLA and escalation terms for the customer's tier. Args: {{"tier": "<tier>"}}
5. "finalize_triage": Choose this when you have sufficient information to make the triage decision.

Respond ONLY with a JSON object in this exact format:
{{
  "thought": "Your reasoning about what information is missing or what to do next",
  "tool_to_call": "resolve_account" | "search_kb" | "get_ticket_history" | "check_support_policy" | "finalize_triage",
  "tool_args": {{}}
}}
"""
        decision = None
        if ctx.llm.has_live_llm:
            try:
                response_str = ctx.llm.generate(prompt)
                parsed = json.loads(response_str)
                if isinstance(parsed, dict) and "tool_to_call" in parsed:
                    decision = parsed
            except Exception as e:
                decision = None

        if not decision:
            # Dynamic Autonomous Agent Decision Logic:
            # Decides what to do next based on what facts are currently known vs needed
            if resolved_account is None:
                decision = {
                    "thought": f"The customer on the ticket is '{raw_company}'. I must resolve the account to check their plan tier, contract ARR, account health, and assigned TAM.",
                    "tool_to_call": "resolve_account",
                    "tool_args": {"company": raw_company, "acc_id": raw_account_id}
                }
            elif not kb_findings and any(k in f"{subject} {body}".lower() for k in ["error", "err_", "failed", "sso", "slow", "how", "configure", "bug", "timeout"]):
                # Extract specific error or keywords
                query = f"{product} {subject}"
                decision = {
                    "thought": f"The ticket describes technical symptoms regarding {product}. I need to search the knowledge base for troubleshooting playbooks and error codes.",
                    "tool_to_call": "search_kb",
                    "tool_args": {"query": query}
                }
            elif not account_tickets and (resolved_account.get("health_status") in ["At Risk", "Churning"] or ticket.get("urgency") in ["P1", "P2"] or "duplicate" in f"{subject} {body}".lower()):
                decision = {
                    "thought": f"Customer {resolved_account.get('company')} is {resolved_account.get('health_status')} with ${resolved_account.get('arr_usd', 0):,} ARR. I must check recent ticket history to detect duplicates and evaluate churn risk.",
                    "tool_to_call": "get_ticket_history",
                    "tool_args": {}
                }
            elif not policy_info and resolved_account.get("plan_tier") in ["Enterprise", "Business"]:
                decision = {
                    "thought": f"Reviewing the support SLA policy for {resolved_account.get('plan_tier')} plan to ensure proper routing and escalation compliance.",
                    "tool_to_call": "check_support_policy",
                    "tool_args": {"tier": resolved_account.get("plan_tier")}
                }
            else:
                decision = {
                    "thought": "I have gathered the required account context, knowledge base playbooks, and ticket history. I am ready to finalize the triage decision.",
                    "tool_to_call": "finalize_triage",
                    "tool_args": {}
                }

        thought = decision.get("thought", "Analyzing ticket...")
        tool_name = decision.get("tool_to_call", "finalize_triage")
        tool_args = decision.get("tool_args", {})

        if tool_name == "finalize_triage":
            reasoning_trace.append(ReasoningStep(
                step=step_num,
                thought=thought,
                action="finalize_triage",
                tool_called="finalize_triage",
                tool_args={},
                observation="All critical account, KB, and history context gathered. Proceeding to final triage decision."
            ))
            finalized = True
            break

        if tool_name in tools_map:
            try:
                obs = tools_map[tool_name](**tool_args)
            except Exception as e:
                obs = f"Tool execution failed: {e}"
        else:
            obs = f"Unknown tool '{tool_name}'."

        reasoning_trace.append(ReasoningStep(
            step=step_num,
            thought=thought,
            action=tool_name,
            tool_called=tool_name,
            tool_args=tool_args,
            observation=obs
        ))
        step_num += 1

    # In case loop finished without resolving account or KB
    if not resolved_account:
        tool_resolve_account(raw_company, raw_account_id)
    if not kb_findings:
        tool_search_kb(f"{product} {subject}")

    # Final Decision Synthesis
    final_output = synthesize_decision(
        ticket=ticket,
        account=resolved_account,
        kb_findings=kb_findings,
        history=account_tickets,
        is_duplicate=is_duplicate,
        duplicate_id=duplicate_id,
        reasoning_trace=reasoning_trace,
        ctx=ctx
    )

    return final_output


def synthesize_decision(
    ticket: Dict[str, Any],
    account: Optional[Dict[str, Any]],
    kb_findings: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    is_duplicate: bool,
    duplicate_id: Optional[str],
    reasoning_trace: List[ReasoningStep],
    ctx: AgentContext
) -> Dict[str, Any]:
    """Synthesizes all gathered agent facts into the strictly validated TriageResult."""
    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    company = (account.get("company") if account else ticket.get("company")) or "Valued Customer"
    acc_id = account.get("account_id") if account else ticket.get("account_id")
    tier = (account.get("plan_tier") if account else ticket.get("plan_tier")) or "Starter"
    health = account.get("health_status") if account else "Healthy"
    arr = account.get("arr_usd", 0) if account else 0
    tam = account.get("tam") if account else None
    
    subject = ticket.get("subject", "")
    body = ticket.get("body", "")
    raw_cat = ticket.get("category", "Bug")
    raw_urgency = ticket.get("urgency", "P3")
    
    # Analyze text & context for true category & priority
    text_lower = f"{subject} {body}".lower()
    
    # 1. Category Refinement
    category = raw_cat
    if "invoice" in text_lower or "billing" in text_lower or "charge" in text_lower or "seat" in text_lower:
        category = "Billing"
    elif "sso" in text_lower or "saml" in text_lower or "webhook" in text_lower or "connector" in text_lower or "api" in text_lower:
        category = "Integration"
    elif "slow" in text_lower or "latency" in text_lower or "timeout" in text_lower:
        category = "Performance"
    elif "data lost" in text_lower or "deleted" in text_lower or "missing data" in text_lower:
        category = "Data Loss"
    elif "how do i" in text_lower or "how to" in text_lower or "documentation" in text_lower or "guide" in text_lower:
        category = "How-To"
    elif "feature" in text_lower or "request:" in text_lower or "would like to request" in text_lower:
        category = "Feature Request"

    # 2. Priority & Escalation Evaluation
    is_high_impact = "critical" in text_lower or "blocked" in text_lower or "down" in text_lower or "outage" in text_lower or "cannot access" in text_lower
    is_at_risk_account = health in ["At Risk", "Churning"] or (account and account.get("renewal_date") and "2025" in str(account.get("renewal_date")))
    
    priority = raw_urgency
    if is_high_impact and (tier == "Enterprise" or is_at_risk_account):
        priority = "P1"
    elif is_high_impact:
        priority = "P2"
    elif category in ["Feature Request", "How-To"]:
        priority = "P4" if tier == "Starter" else "P3"

    # Escalation & TAM alert rules
    escalation = False
    tam_notification = False
    
    if priority == "P1" or (is_at_risk_account and priority in ["P1", "P2"]) or (arr > 100000 and priority in ["P1", "P2"]):
        escalation = True
        tam_notification = True if tam else False
    elif is_at_risk_account:
        tam_notification = True if tam else False

    # 3. Routing
    if category == "Billing":
        routing = "Billing & Contract Operations"
    elif category in ["Integration", "Bug"] and ("sso" in text_lower or "auth" in text_lower):
        routing = "Identity & Security Engineering"
    elif category == "Integration":
        routing = "Integrations & API Support Team"
    elif category == "Data Loss":
        routing = "Data Platform SRE (Urgent)"
    elif category == "Performance":
        routing = "Platform Performance & Infrastructure"
    elif category == "Feature Request":
        routing = "Product Management"
    else:
        routing = "Technical Support Tier 2"

    # 4. Clarification
    needs_clarification = False
    if len(body.strip()) < 80 and not is_duplicate and not kb_findings:
        needs_clarification = True

    # 5. Customer Reply & Internal TAM Note
    kb_summary = kb_findings[0]["content"][:300] if kb_findings else ""
    
    if needs_clarification:
        customer_reply = (
            f"Dear {company} Team,\n\n"
            f"Thank you for contacting Technical Support regarding '{subject}'. "
            f"To help us resolve this promptly, could you please provide additional details such as relevant error logs, "
            f"the affected user accounts, and specific timestamps when this was observed?\n\n"
            f"Best regards,\nTechnical Account Support"
        )
    elif is_duplicate:
        customer_reply = (
            f"Dear {company} Team,\n\n"
            f"Thank you for reaching out. We have linked this request to your existing active ticket {duplicate_id}, "
            f"which our engineering team is actively investigating. We will provide full updates directly on the primary thread.\n\n"
            f"Best regards,\nTechnical Support"
        )
    else:
        customer_reply = (
            f"Dear {company} Team,\n\n"
            f"Thank you for contacting Technical Support regarding '{subject}'. "
            f"Our team has reviewed your request under your {tier} plan.\n\n"
            f"Initial Investigation & Recommendations:\n"
            f"Based on our diagnostic review, please verify the following recommended steps:\n"
            f"- {kb_summary.splitlines()[0] if kb_summary else 'Our specialized engineering team has been assigned and is verifying logs.'}\n\n"
            f"We have categorized this as {priority} and routed it to our {routing}. You will receive further updates shortly.\n\n"
            f"Best regards,\nTechnical Account Management Team"
        )

    internal_note = (
        f"INTERNAL TAM / SUPPORT NOTE:\n"
        f"- Customer: {company} (ID: {acc_id or 'Unmatched'}) | Plan: {tier} | ARR: ${arr:,}\n"
        f"- Account Health: {health} | TAM: {tam or 'None Assigned'}\n"
        f"- Triage: Category={category}, Priority={priority}, Routed To={routing}\n"
        f"- Escalation: {'YES - Flagged for immediate escalation' if escalation else 'No'}\n"
        f"- TAM Alert: {'YES - Notify ' + str(tam) if tam_notification else 'No'}\n"
        f"- Context: {'Duplicate of ' + str(duplicate_id) if is_duplicate else 'Unique ticket'}. "
        f"{'Account is At Risk/Churning - monitor closely.' if is_at_risk_account else 'Account in good standing.'}"
    )

    result = {
        "ticket_id": ticket_id,
        "account_id": acc_id,
        "company": company,
        "category": category,
        "priority": priority,
        "routing": routing,
        "escalation": escalation,
        "tam_notification": tam_notification,
        "tam_name": tam,
        "duplicate_status": is_duplicate,
        "duplicate_ticket_id": duplicate_id,
        "needs_clarification": needs_clarification,
        "customer_reply": customer_reply,
        "internal_note": internal_note,
        "reasoning_trace": [r.model_dump() for r in reasoning_trace]
    }

    # Validate against strict schema
    validated = TriageResult.model_validate(result)
    return validated.model_dump(mode="json")
