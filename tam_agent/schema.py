"""
tam_agent/schema.py - Required Output Format and Schema Validator
"""

from enum import Enum
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator


class CategoryEnum(str, Enum):
    BUG = "Bug"
    FEATURE_REQUEST = "Feature Request"
    HOW_TO = "How-To"
    PERFORMANCE = "Performance"
    BILLING = "Billing"
    INTEGRATION = "Integration"
    ONBOARDING = "Onboarding"
    DATA_LOSS = "Data Loss"


class PriorityEnum(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ReasoningStep(BaseModel):
    step: int = Field(..., description="Step sequence number (1-indexed)")
    thought: str = Field(..., description="The agent's internal reasoning or goal for this step")
    action: Optional[str] = Field(None, description="Action taken or tool invoked")
    tool_called: Optional[str] = Field(None, description="Name of the tool called")
    tool_args: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arguments passed to the tool")
    observation: Optional[str] = Field(None, description="Result or observation received from the tool/environment")


class TriageResult(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier")
    account_id: Optional[str] = Field(None, description="Resolved account identifier (e.g. ACC-xxxx)")
    company: Optional[str] = Field(None, description="Customer company name")
    
    # Decisions
    category: CategoryEnum = Field(..., description="Triage category")
    priority: PriorityEnum = Field(..., description="Triaged priority: P1, P2, P3, P4")
    routing: str = Field(..., description="Target team or queue, e.g. 'Integrations Team', 'Core Platform Engineering', 'TAM', 'Billing'")
    escalation: bool = Field(default=False, description="Whether this ticket requires formal escalation")
    tam_notification: bool = Field(default=False, description="Whether the assigned TAM must be notified")
    tam_name: Optional[str] = Field(None, description="Assigned TAM name if applicable")
    
    # Duplicate & Clarification status
    duplicate_status: bool = Field(default=False, description="Whether ticket is a duplicate of another ticket")
    duplicate_ticket_id: Optional[str] = Field(None, description="Ticket ID of the duplicate, if applicable")
    needs_clarification: bool = Field(default=False, description="Whether more information/logs/reproduction steps are needed")
    
    # Drafts
    customer_reply: str = Field(..., min_length=10, description="Customer-facing reply draft")
    internal_note: str = Field(..., min_length=10, description="Internal TAM / engineering handoff note")
    
    # Trace
    reasoning_trace: List[ReasoningStep] = Field(..., min_length=1, description="Step-by-step trace of agent reasoning and tool calls")

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in {"P1", "P2", "P3", "P4"}:
                return v_upper
            # Fallback for common priority words
            mapping = {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P4"}
            return mapping.get(v_upper, v)
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_title = v.strip().title()
            for cat in CategoryEnum:
                if cat.value.lower() == v.strip().lower():
                    return cat.value
        return v


def validate_triage_dict(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validates a dictionary against the TriageResult schema."""
    try:
        TriageResult.model_validate(data)
        return True, None
    except Exception as e:
        return False, str(e)
