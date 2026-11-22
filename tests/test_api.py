"""REST adapter tests for the React frontend.

These exercise the FastAPI layer end to end while relying on the deterministic
planner (no Gemini calls).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import services
from api.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def auth() -> dict[str, str]:
    response = client.post("/api/auth/demo")
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture(scope="module")
def profile() -> dict:
    return {
        "name": "API Test User",
        "age": 32,
        "gender": "female",
        "height_cm": 162,
        "weight_kg": 62,
        "activity_level": "moderately_active",
        "fitness_goal": "weight_loss",
        "diet_type": "veg",
        "allergies": ["peanuts"],
        "disliked_foods": ["cucumber"],
        "cuisine_preferences": ["South Indian"],
        "budget": "medium",
        "cooking_time_minutes": 30,
        "health_conditions": [],
    }


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_required(auth: dict[str, str]) -> None:
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers=auth).status_code == 200


def test_signup_and_duplicate() -> None:
    email = "pytest-user@nutrition.local"
    client.post("/api/auth/signout")
    created = client.post(
        "/api/auth/signup",
        json={"name": "Pytest", "email": email, "password": "secret123"},
    )
    if created.status_code == 409:
        # Account from an earlier run — sign-in must still work.
        created = client.post(
            "/api/auth/signin", json={"email": email, "password": "secret123"}
        )
    assert created.status_code == 200
    assert created.json()["user"]["email"] == email
    duplicate = client.post(
        "/api/auth/signup",
        json={"name": "Pytest", "email": email, "password": "secret123"},
    )
    assert duplicate.status_code == 409
    bad = client.post(
        "/api/auth/signin", json={"email": email, "password": "wrong-password"}
    )
    assert bad.status_code == 401


def test_profile_and_targets(auth: dict[str, str], profile: dict) -> None:
    assert client.put("/api/profile", json=profile, headers=auth).status_code == 200
    saved = client.get("/api/profile", headers=auth).json()
    assert saved["diet_type"] == "veg"
    targets = client.post("/api/targets", json=profile, headers=auth)
    assert targets.status_code == 200
    assert targets.json()["calorie_target"] > 1200


def test_generate_plan(auth: dict[str, str], profile: dict) -> None:
    response = client.post(
        "/api/plans/generate", json={"profile": profile, "mode": "fast"}, headers=auth
    )
    assert response.status_code == 200, response.text[:500]
    data = response.json()
    assert len(data["plan"]["days"]) == 7
    for day in data["plan"]["days"]:
        assert set(day["meals"]) == {"breakfast", "lunch", "snack", "dinner"}
        for meal in day["meals"].values():
            assert meal["total_calories"] > 0
            assert meal["steps"]
            assert meal["why"]
            assert meal["image"].startswith("/images/")


def test_grocery_insights_and_export(auth: dict[str, str]) -> None:
    current = client.get("/api/plans/current", headers=auth).json()
    plan_id = current["plan_id"]
    grocery = client.get("/api/grocery", params={"plan_id": plan_id}, headers=auth)
    assert grocery.status_code == 200
    assert len(grocery.json()["items"]) > 5
    insights = client.get("/api/insights", params={"plan_id": plan_id}, headers=auth)
    assert insights.status_code == 200
    assert len(insights.json()["micronutrients"]) == 17
    exported = client.get(f"/api/plans/{plan_id}/export", headers=auth)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/pdf")
    assert "nutriplan-7-day-plan.pdf" in exported.headers.get("content-disposition", "")
    assert exported.content.startswith(b"%PDF")


def test_partial_swap_and_regenerate(auth: dict[str, str]) -> None:
    current = client.get("/api/plans/current", headers=auth).json()
    plan_id = current["plan_id"]
    original = current["plan"]["days"][0]["meals"]["lunch"]
    original_name = original["items"][0]["food_name"]
    options = client.get(
        "/api/foods/substitutes", params={"food_name": original_name}, headers=auth
    ).json()["items"]
    replacement = next((o["food_name"] for o in options if o["food_name"] != original_name), "Basmati Rice")

    swapped = client.post(
        f"/api/plans/{plan_id}/swap",
        json={"plan_id": plan_id, "day": "Monday", "meal": "lunch", "food_name": replacement},
        headers=auth,
    )
    assert swapped.status_code == 200, swapped.text[:300]
    assert swapped.json()["plan"]["days"][0]["meals"]["lunch"] != original

    regenerated = client.post(
        f"/api/plans/{plan_id}/regenerate",
        json={"plan_id": plan_id, "day": "Tuesday", "meal": "dinner"},
        headers=auth,
    )
    assert regenerated.status_code == 200, regenerated.text[:300]
    plan = regenerated.json()["plan"]
    assert plan["days"][0]["meals"]["lunch"] == swapped.json()["plan"]["days"][0]["meals"]["lunch"]


def test_foods_and_substitutes(auth: dict[str, str]) -> None:
    search = client.get("/api/foods/search", params={"q": "dal", "limit": 5}, headers=auth)
    assert search.status_code == 200
    assert 0 < search.json()["count"] <= 5
    name = search.json()["items"][0]["food_name"]
    subs = client.get("/api/foods/substitutes", params={"food_name": name}, headers=auth)
    assert subs.status_code == 200


def test_chat_with_citations(auth: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        services,
        "_rag_details",
        lambda _: [{"document": "icmr.pdf", "page": 12, "text": "Protein supports muscle repair."}],
    )
    response = client.post(
        "/api/chat",
        json={"message": "How can I improve my iron intake?", "history": []},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"]
    assert body["citations"][0]["source"].endswith(".pdf")
    assert client.get("/api/chat/history", headers=auth).json()["messages"]


def test_checklist_favorites_and_history(auth: dict[str, str]) -> None:
    checked = client.post("/api/grocery/check", json={"rice": True}, headers=auth)
    assert checked.json()["checked"]["rice"] is True
    fav = client.post("/api/favorites", json={"key": "monday:lunch"}, headers=auth)
    assert "monday:lunch" in fav.json()["keys"]
    fav2 = client.post("/api/favorites", json={"key": "monday:lunch"}, headers=auth)
    assert "monday:lunch" not in fav2.json()["keys"]
    added = client.post(
        "/api/history",
        json={"food_name": "Dal", "total_calories": 320, "day": "Monday"},
        headers=auth,
    )
    assert len(added.json()["entries"]) >= 1


def test_email_validation() -> None:
    response = client.post(
        "/api/auth/signup",
        json={"name": "Bad", "email": "not-an-email", "password": "secret123"},
    )
    assert response.status_code == 422
