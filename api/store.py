"""Small JSON-backed persistence layer for the REST service.

This is deliberately dependency-free: it stores demo/local product state
(users, tokens, profiles, plans, chats and shopping lists) in ``.api_data``.
The nutrition engine itself remains stateless and unchanged.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / ".api_data"
DATA_FILE = DATA_DIR / "store.json"

_EMPTY: dict[str, Any] = {
    "users": {},
    "tokens": {},
    "profiles": {},
    "plans": {},
    "chats": {},
    "favorites": {},
    "eaten": {},
    "checklist": {},
}

_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


def _load() -> dict[str, Any]:
    if not DATA_FILE.exists():
        data = {key: dict(value) for key, value in _EMPTY.items()}
        # Seeded demo account keeps the "try the product" flow instant.
        salt = secrets.token_hex(16)
        data["users"]["demo-user"] = {
            "id": "demo-user",
            "name": "Demo User",
            "email": "demo@nutrition.local",
            "salt": salt,
            "password_hash": _hash_password("demo1234", salt),
            "created_at": _now(),
        }
        _save(data)
        return data
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    data = {key: dict(value) for key, value in _EMPTY.items()}
    for key, value in raw.items():
        if key in data and isinstance(value, dict):
            data[key].update(value)
    return data


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA_FILE)


def _mutate(fn):
    """Run a store operation under a lock and persist afterwards."""
    def wrapper(*args, **kwargs):
        with _LOCK:
            data = _load()
            result = fn(data, *args, **kwargs)
            _save(data)
            return result
    return wrapper


# ── Auth ───────────────────────────────────────────────────────────────────────

@_mutate
def create_user(data: dict[str, Any], name: str, email: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    if any(str(u.get("email", "")).lower() == email for u in data["users"].values()):
        raise ValueError("An account with this email already exists.")
    user_id = uuid.uuid4().hex
    salt = secrets.token_hex(16)
    data["users"][user_id] = {
        "id": user_id,
        "name": name.strip(),
        "email": email,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": _now(),
    }
    return public_user(data["users"][user_id])


@_mutate
def authenticate(data: dict[str, Any], email: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    user = next(
        (u for u in data["users"].values() if str(u.get("email", "")).lower() == email),
        None,
    )
    if user is None or not secrets.compare_digest(
        str(user.get("password_hash")), _hash_password(password, str(user.get("salt", "")))
    ):
        raise ValueError("Incorrect email or password.")
    return public_user(user)


def public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(user["id"]),
        "name": str(user["name"]),
        "email": str(user["email"]),
    }


@_mutate
def issue_token(data: dict[str, Any], user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    data["tokens"][token] = user_id
    return token


def resolve_token(token: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        data = _load()
        user_id = data["tokens"].get(token)
        user = data["users"].get(user_id) if user_id else None
        return public_user(user) if user else None


@_mutate
def revoke_token(data: dict[str, Any], token: str) -> None:
    data["tokens"].pop(token, None)


# ── Profiles ───────────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        return _load()["profiles"].get(user_id)


@_mutate
def save_profile(data: dict[str, Any], user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    data["profiles"][user_id] = {**profile, "updated_at": _now()}
    return data["profiles"][user_id]


# ── Plans ──────────────────────────────────────────────────────────────────────

@_mutate
def save_plan(
    data: dict[str, Any],
    user_id: str,
    *,
    plan: dict[str, Any],
    raw_plan: dict[str, Any],
    profile: dict[str, Any],
    targets: dict[str, Any],
    mode: str,
) -> str:
    plan_id = uuid.uuid4().hex
    data["plans"][plan_id] = {
        "id": plan_id,
        "user_id": user_id,
        "plan": plan,
        "raw_plan": raw_plan,
        "profile": profile,
        "targets": targets,
        "mode": mode,
        "created_at": _now(),
    }
    return plan_id


def get_plan(user_id: str, plan_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    with _LOCK:
        plans = _load()["plans"]
        if plan_id:
            record = plans.get(plan_id)
            return record if record and record.get("user_id") == user_id else None
        owned = [p for p in plans.values() if p.get("user_id") == user_id]
        return max(owned, key=lambda p: p.get("created_at", "")) if owned else None


def list_plans(user_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        plans = [
            p for p in _load()["plans"].values() if p.get("user_id") == user_id
        ]
    return sorted(plans, key=lambda p: p.get("created_at", ""), reverse=True)


@_mutate
def update_plan(
    data: dict[str, Any], user_id: str, plan_id: str, *, plan: dict, raw_plan: dict
) -> bool:
    record = data["plans"].get(plan_id)
    if not record or record.get("user_id") != user_id:
        return False
    record["plan"] = plan
    record["raw_plan"] = raw_plan
    record["updated_at"] = _now()
    return True


@_mutate
def delete_plan(data: dict[str, Any], user_id: str, plan_id: str) -> bool:
    record = data["plans"].get(plan_id)
    if not record or record.get("user_id") != user_id:
        return False
    data["plans"].pop(plan_id, None)
    return True


# ── Chat / favorites / history / checklist ────────────────────────────────────

def get_chat(user_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        return list(_load()["chats"].get(user_id, []))


@_mutate
def append_chat(data: dict[str, Any], user_id: str, messages: list[dict[str, Any]]) -> None:
    data["chats"].setdefault(user_id, []).extend(messages[-80:])


@_mutate
def clear_chat(data: dict[str, Any], user_id: str) -> None:
    data["chats"][user_id] = []


def get_favorites(user_id: str) -> list[str]:
    with _LOCK:
        return list(_load()["favorites"].get(user_id, []))


@_mutate
def toggle_favorite(data: dict[str, Any], user_id: str, key: str) -> list[str]:
    items = data["favorites"].setdefault(user_id, [])
    if key in items:
        items.remove(key)
    else:
        items.append(key)
    return list(items)


def get_eaten(user_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        return list(_load()["eaten"].get(user_id, []))


@_mutate
def add_eaten(data: dict[str, Any], user_id: str, entry: dict[str, Any]) -> None:
    items = data["eaten"].setdefault(user_id, [])
    items.insert(0, {**entry, "id": uuid.uuid4().hex, "eaten_at": _now()})
    del items[200:]


def get_checklist(user_id: str) -> dict[str, bool]:
    with _LOCK:
        return dict(_load()["checklist"].get(user_id, {}))


@_mutate
def set_checklist(data: dict[str, Any], user_id: str, checked: dict[str, bool]) -> dict[str, bool]:
    data["checklist"][user_id] = {str(k): bool(v) for k, v in checked.items()}
    return dict(data["checklist"][user_id])
