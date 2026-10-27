"""
tam_agent/data.py - Data loaders and lookup utilities for tickets and accounts.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Lowercase and strip punctuation/extra whitespace
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


class DataLoader:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.tickets: List[Dict[str, Any]] = []
        self.accounts: List[Dict[str, Any]] = []
        self.tickets_by_id: Dict[str, Dict[str, Any]] = {}
        self.accounts_by_id: Dict[str, Dict[str, Any]] = {}
        self.accounts_by_company: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self.load()

    def load(self):
        tickets_path = self.data_dir / "tickets.json"
        accounts_path = self.data_dir / "accounts.json"

        if tickets_path.exists():
            with open(tickets_path, "r", encoding="utf-8") as f:
                self.tickets = json.load(f)
            self.tickets_by_id = {t["ticket_id"]: t for t in self.tickets if "ticket_id" in t}

        if accounts_path.exists():
            with open(accounts_path, "r", encoding="utf-8") as f:
                self.accounts = json.load(f)
            self.accounts_by_id = {a["account_id"]: a for a in self.accounts if "account_id" in a}
            for a in self.accounts:
                c_name = a.get("company", "")
                if c_name:
                    self.accounts_by_company[normalize_text(c_name)] = a

        self._loaded = True

    def resolve_account(self, account_id: Optional[str] = None, company_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Resolves an account even if account_id is blank, outdated, or mismatched.
        First tries company name lookup (most reliable in this dataset), then direct account_id.
        """
        if company_name:
            norm_comp = normalize_text(company_name)
            if norm_comp in self.accounts_by_company:
                return self.accounts_by_company[norm_comp]
            # Partial match if company name has suffix like Inc, LLC, Corp
            for c_norm, acc in self.accounts_by_company.items():
                if norm_comp in c_norm or c_norm in norm_comp:
                    return acc

        if account_id and account_id in self.accounts_by_id:
            return self.accounts_by_id[account_id]

        return None

    def get_account_tickets(
        self,
        account_id: Optional[str] = None,
        company_name: Optional[str] = None,
        current_ticket_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetches related historical tickets for an account or company to spot trends or duplicates.
        """
        acc = self.resolve_account(account_id, company_name)
        comp_norm = normalize_text(company_name or (acc.get("company") if acc else ""))
        true_acc_id = acc.get("account_id") if acc else account_id

        related = []
        for t in self.tickets:
            if current_ticket_id and t.get("ticket_id") == current_ticket_id:
                continue
            
            # Match by true account id or company name
            t_comp_norm = normalize_text(t.get("company", ""))
            if (true_acc_id and t.get("account_id") == true_acc_id) or (comp_norm and t_comp_norm == comp_norm):
                related.append(t)
                if len(related) >= limit:
                    break
        return related

    def check_duplicate(
        self,
        ticket: Dict[str, Any],
        historical_tickets: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[str]]:
        """
        Heuristic to detect if ticket is a duplicate of a recent ticket from the same customer.
        """
        curr_subject_words = set(normalize_text(ticket.get("subject", "")).split())
        curr_product = (ticket.get("product") or "").lower()

        for h in historical_tickets:
            if h.get("ticket_id") == ticket.get("ticket_id"):
                continue
            h_product = (h.get("product") or "").lower()
            if curr_product and h_product and curr_product == h_product:
                h_words = set(normalize_text(h.get("subject", "")).split())
                overlap = curr_subject_words.intersection(h_words)
                # If high word overlap and open status
                if len(overlap) >= 3 and len(overlap) / max(len(curr_subject_words), 1) > 0.6:
                    return True, h.get("ticket_id")

        return False, None
