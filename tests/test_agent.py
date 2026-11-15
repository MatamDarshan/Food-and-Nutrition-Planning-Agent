"""
tests/test_agent.py
-------------------
Integration and workflow tests for the LangGraph agent:
- Graph structure & compilation
- Profile validation node
- Nutrition calculation node
- JSON meal plan extraction
- Meal plan validation node
- Plan revision node with retry limit
- Graceful fallback node
- Conditional edge transitions
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from agent.graph import (
    create_agent_graph,
    extract_meal_plan_json,
    profile_validation_node,
    nutrition_calculation_node,
    meal_validation_node,
    plan_revision_node,
    final_response_node,
    route_profile_validation,
    route_agent_output,
    route_validation_outcome,
)


class TestAgentNodes:
    def test_graph_compilation(self):
        graph = create_agent_graph()
        assert graph is not None
        for node in [
            "profile_validation",
            "nutrition_calculation",
            "agent",
            "tools",
            "meal_validation",
            "plan_revision",
            "final_response",
        ]:
            assert node in graph.nodes

    def test_profile_validation_node_valid(self, sample_veg_profile):
        state = {
            "user_profile": sample_veg_profile.model_dump(),
            "messages": [],
            "revision_count": 0,
        }
        res = profile_validation_node(state)
        assert res.get("error") is None
        assert res.get("user_profile")["name"] == "Arjun"

    def test_profile_validation_node_invalid(self):
        state = {
            "user_profile": {"name": "Bad", "age": 2}, # Age < 10
            "messages": [],
            "revision_count": 0,
        }
        res = profile_validation_node(state)
        assert res.get("error") is not None

    def test_nutrition_calculation_node(self, sample_veg_profile):
        state = {
            "user_profile": sample_veg_profile.model_dump(),
            "messages": [],
            "error": None,
            "revision_count": 0,
        }
        res = nutrition_calculation_node(state)
        targets = res.get("nutrition_targets")
        assert targets is not None
        assert targets["calorie_target"] > 1200.0
        assert len(res["messages"]) == 1

    def test_extract_meal_plan_json(self):
        text = """
        Plan:
        ```json
        {
            "breakfast": [{"food_name": "Idli", "quantity_g": 100}],
            "lunch": [{"food_name": "Dal Tadka", "quantity_g": 150}],
            "snack": [{"food_name": "Apple", "quantity_g": 100}],
            "dinner": [{"food_name": "Roti", "quantity_g": 60}]
        }
        ```
        """
        extracted = extract_meal_plan_json(text)
        assert extracted is not None
        assert "breakfast" in extracted

    def test_plan_revision_retry_increment(self):
        state = {
            "validation_result": {
                "is_valid": False,
                "issues": ["Low protein."],
                "planned_calories": 1500,
                "target_calories": 1800,
            },
            "revision_count": 1,
            "messages": [],
        }
        res = plan_revision_node(state)
        assert res["revision_count"] == 2
        assert "Low protein." in res["messages"][0].content


class TestRoutingLogic:
    def test_route_profile_validation(self):
        assert route_profile_validation({"error": None}) == "nutrition_calculation"
        assert route_profile_validation({"error": "Failed"}) == "final_response"

    def test_route_agent_output(self):
        msg_tool = AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "1"}])
        msg_text = AIMessage(content="Hello")
        assert route_agent_output({"messages": [msg_tool]}) == "tools"
        assert route_agent_output({"messages": [msg_text]}) == "meal_validation"

    def test_route_validation_outcome_retry(self):
        # 1st failure -> plan_revision
        assert (
            route_validation_outcome({
                "validation_result": {"is_valid": False},
                "revision_count": 0,
            })
            == "plan_revision"
        )
        # 2nd failure reached max revisions (2) -> final_response
        assert (
            route_validation_outcome({
                "validation_result": {"is_valid": False},
                "revision_count": 2,
            })
            == "final_response"
        )
        # Valid -> final_response
        assert (
            route_validation_outcome({"validation_result": {"is_valid": True}})
            == "final_response"
        )
