"""FastAPI entry point for the React nutrition product.

Run locally: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from api import services, store
from api.schemas import (
    ChatRequest,
    PlanGenerateRequest,
    RegenerateMealRequest,
    ProfileIn,
    SignInRequest,
    SignUpRequest,
    SwapMealRequest,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "frontend" / "dist"

app = FastAPI(
    title="NutriPlan API",
    description="REST adapter for the ICMR-NIN nutrition planning engine.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Invalid request.", "errors": errors})


def current_user(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = store.resolve_token(authorization.split(" ", 1)[1].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Your session expired. Please sign in again.")
    return user


def _require_plan(user_id: str, plan_id: Optional[str]) -> dict[str, Any]:
    record = store.get_plan(user_id, plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Meal plan not found.")
    return record


def _default_profile(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "age": 30,
        "gender": "female",
        "height_cm": 165.0,
        "weight_kg": 65.0,
        "activity_level": "moderately_active",
        "fitness_goal": "maintenance",
        "diet_type": "veg",
        "allergies": [],
        "disliked_foods": [],
        "cuisine_preferences": [],
        "budget": "medium",
        "cooking_time_minutes": 30,
        "health_conditions": [],
    }


# ── Health / auth ─────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "NutriPlan API"}


@app.post("/api/auth/signup")
def signup(payload: SignUpRequest) -> dict[str, Any]:
    try:
        user = store.create_user(payload.name, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"token": store.issue_token(user["id"]), "user": user}


@app.post("/api/auth/signin")
def signin(payload: SignInRequest) -> dict[str, Any]:
    try:
        user = store.authenticate(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"token": store.issue_token(user["id"]), "user": user}


@app.post("/api/auth/demo")
def demo_signin() -> dict[str, Any]:
    user = store.authenticate("demo@nutrition.local", "demo1234")
    return {"token": store.issue_token(user["id"]), "user": user}


@app.get("/api/auth/me")
def me(user: dict[str, str] = Depends(current_user)) -> dict[str, str]:
    return user


@app.post("/api/auth/signout")
def signout(authorization: Optional[str] = Header(default=None)) -> dict[str, bool]:
    if authorization and authorization.lower().startswith("bearer "):
        store.revoke_token(authorization.split(" ", 1)[1].strip())
    return {"ok": True}


# ── Profile / targets ─────────────────────────────────────────────────────────

@app.get("/api/profile")
def get_profile(user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    return store.get_profile(user["id"]) or _default_profile(user["name"])


@app.put("/api/profile")
def put_profile(
    payload: ProfileIn, user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    return store.save_profile(user["id"], payload.model_dump())


@app.post("/api/targets")
def compute_targets(
    payload: ProfileIn, user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    profile = services.engine_profile(payload.model_dump())
    return services.targets_for(profile)


# ── Plans ─────────────────────────────────────────────────────────────────────

@app.post("/api/plans/generate")
def generate(
    payload: PlanGenerateRequest, user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    profile_in = payload.profile.model_dump()
    store.save_profile(user["id"], profile_in)
    profile = services.engine_profile(profile_in)
    targets = services.targets_for(profile)
    plan, raw_plan = services.generate_plan(profile, targets, payload.mode)
    plan_id = store.save_plan(
        user["id"],
        plan=plan,
        raw_plan=raw_plan,
        profile=profile,
        targets=targets,
        mode=payload.mode,
    )
    return {"plan_id": plan_id, "plan": plan, "targets": targets, "mode": payload.mode}


@app.get("/api/plans/current")
def current_plan(user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    record = store.get_plan(user["id"])
    if not record:
        return {"plan": None, "plan_id": None}
    return {
        "plan_id": record["id"],
        "plan": record["plan"],
        "targets": record["targets"],
        "mode": record.get("mode", "fast"),
        "created_at": record.get("created_at"),
    }


@app.get("/api/plans")
def list_plans(user: dict[str, str] = Depends(current_user)) -> list[dict[str, Any]]:
    return [
        {
            "plan_id": p["id"],
            "created_at": p.get("created_at"),
            "mode": p.get("mode"),
            "days": len((p.get("plan") or {}).get("days") or []),
        }
        for p in store.list_plans(user["id"])
    ]


@app.get("/api/plans/{plan_id}")
def get_plan_endpoint(
    plan_id: str, user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    record = _require_plan(user["id"], plan_id)
    return {
        "plan_id": record["id"],
        "plan": record["plan"],
        "targets": record["targets"],
        "mode": record.get("mode", "fast"),
    }


@app.post("/api/plans/{plan_id}/regenerate")
def regenerate(
    plan_id: str,
    payload: RegenerateMealRequest,
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    record = _require_plan(user["id"], plan_id)
    plan, raw = services.regenerate_meal(record, payload.day, payload.meal)
    store.update_plan(user["id"], plan_id, plan=plan, raw_plan=raw)
    return {"plan_id": plan_id, "plan": plan}


@app.post("/api/plans/{plan_id}/swap")
def swap_meal(
    plan_id: str,
    payload: SwapMealRequest,
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    record = _require_plan(user["id"], plan_id)
    plan, raw = services.swap_food(record, payload.day, payload.meal, payload.food_name)
    store.update_plan(user["id"], plan_id, plan=plan, raw_plan=raw)
    return {"plan_id": plan_id, "plan": plan}


@app.get("/api/plans/{plan_id}/recipe")
def recipe(
    plan_id: str,
    day: str = Query(...),
    meal: str = Query(...),
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    plan = _require_plan(user["id"], plan_id)["plan"]
    for item in plan.get("days") or []:
        if str(item.get("day_name", "")).lower() == day.lower():
            found = (item.get("meals") or {}).get(meal.lower())
            if found:
                return found
    raise HTTPException(status_code=404, detail="Meal not found in this plan.")


@app.get("/api/plans/{plan_id}/export")
def export(
    plan_id: str, user: dict[str, str] = Depends(current_user)
) -> Response:
    record = _require_plan(user["id"], plan_id)
    content = services.export_plan(record["plan"], record["profile"])
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="nutriplan-7-day-plan.pdf"'},
    )


@app.delete("/api/plans/{plan_id}")
def remove_plan(
    plan_id: str, user: dict[str, str] = Depends(current_user)
) -> dict[str, bool]:
    if not store.delete_plan(user["id"], plan_id):
        raise HTTPException(status_code=404, detail="Meal plan not found.")
    return {"ok": True}


# ── Foods ─────────────────────────────────────────────────────────────────────

@app.get("/api/foods/search")
def foods_search(
    q: str = Query(default=""),
    diet: str = Query(default="all"),
    meal: str = Query(default=""),
    category: str = Query(default=""),
    limit: int = Query(default=24, ge=1, le=60),
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    items = services.search_foods(q, diet, meal, category, limit)
    return {"items": items, "count": len(items)}


@app.get("/api/foods/substitutes")
def food_substitutes(
    food_name: str = Query(...),
    meal: str = Query(default=""),
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    items = services.substitutes(food_name, store.get_profile(user["id"]), meal)
    return {"items": items, "count": len(items)}


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(
    payload: ChatRequest, user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    profile = store.get_profile(user["id"])
    record = store.get_plan(user["id"], payload.plan_id)
    plan = record["plan"] if record else None
    result = services.chat_reply(payload.message, [m.model_dump() for m in payload.history], profile, plan)
    store.append_chat(
        user["id"],
        [
            {"role": "user", "content": payload.message},
            {"role": "assistant", "content": result["reply"], "citations": result["citations"]},
        ],
    )
    return result


@app.get("/api/chat/history")
def chat_history(user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    return {"messages": store.get_chat(user["id"])}


@app.delete("/api/chat/history")
def clear_chat(user: dict[str, str] = Depends(current_user)) -> dict[str, bool]:
    store.clear_chat(user["id"])
    return {"ok": True}


# ── Grocery / favorites / history / insights ─────────────────────────────────

@app.get("/api/grocery")
def grocery(
    plan_id: Optional[str] = Query(default=None),
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    record = _require_plan(user["id"], plan_id)
    return {"items": services.grocery_list(record["plan"]), "checked": store.get_checklist(user["id"])}


@app.post("/api/grocery/check")
def grocery_check(
    payload: dict[str, bool], user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    return {"checked": store.set_checklist(user["id"], payload)}


@app.get("/api/favorites")
def favorites(user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    return {"keys": store.get_favorites(user["id"])}


@app.post("/api/favorites")
def toggle_favorite(
    payload: dict[str, str], user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    if "key" not in payload:
        raise HTTPException(status_code=400, detail="A meal key is required.")
    return {"keys": store.toggle_favorite(user["id"], str(payload["key"]))}


@app.get("/api/history")
def meal_history(user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    return {"entries": store.get_eaten(user["id"])}


@app.post("/api/history")
def add_history(
    payload: dict[str, Any], user: dict[str, str] = Depends(current_user)
) -> dict[str, Any]:
    store.add_eaten(user["id"], payload)
    return {"entries": store.get_eaten(user["id"])}


@app.get("/api/insights")
def nutrition_insights(
    plan_id: Optional[str] = Query(default=None),
    user: dict[str, str] = Depends(current_user),
) -> dict[str, Any]:
    record = _require_plan(user["id"], plan_id)
    return services.insights(record["plan"])


# Serve the built React app from the same origin when available.
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Client-side routing fallback for the React app."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unknown API endpoint.")
        candidate = (DIST_DIR / full_path).resolve()
        if candidate.is_file() and DIST_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
