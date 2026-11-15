"""
agent/state.py
--------------
LangGraph AgentState definition.
Tracks conversation messages, user profile, nutritional targets,
generated meal plans, validation results, and retry counts.
"""

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Global state container for the LangGraph agent workflow."""

    # Chat history / tool messages
    messages: Annotated[list[BaseMessage], add_messages]

    # User details & calculated nutritional targets
    user_profile: Optional[dict[str, Any]]
    nutrition_targets: Optional[dict[str, Any]]

    # Generated meal plan dictionary:
    # {"breakfast": [...], "lunch": [...], "snack": [...], "dinner": [...]}
    meal_plan: Optional[dict[str, Any]]

    # Validation outcome from core/validation.py
    validation_result: Optional[dict[str, Any]]

    # Revision counter for guarded loops
    revision_count: int

    # Final formatted meal plan & advice
    final_response: Optional[str]

    # Optional error message
    error: Optional[str]
