"""
core/profile_wizard.py
----------------------
Headless, one-question-at-a-time profile builder.

This module contains **no Streamlit code**. It is a small, deterministic state
machine that asks for every :class:`~core.user_profile.UserProfile` field in a
friendly order, parses free-form answers (including common aliases such as
``milk`` for ``dairy`` or ``5'7`` for height), retries invalid answers, and
finally hands the collected answers to Pydantic via ``UserProfile(**answers)``.

Keeping the state machine separate means the conversational flow can be unit
tested without running a browser, and the existing form path stays untouched.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.allergens import canonicalize_allergen
from core.user_profile import UserProfile

# ── Constants ───────────────────────────────────────────────────────────────────

KNOWN_ALLERGENS = (
    "gluten", "dairy", "eggs", "fish", "tree_nuts", "peanuts", "soy", "shellfish",
)

_SKIP_TOKENS = frozenset({"", "none", "no", "n/a", "na", "skip", "skip for now", "-"})


# ── Low-level parsing helpers ───────────────────────────────────────────────────

def _clean(raw: object) -> str:
    return re.sub(r"\s+", " ", str(raw or "")).strip()


def _key(value: object) -> str:
    """Normalise a choice answer for alias lookup."""
    return re.sub(r"[\s\-/]+", "_", _clean(value).lower()).strip("_")


def _number(raw: object, label: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", _clean(raw).replace(",", ""))
    if not match:
        raise ValueError(f"Please enter a number for {label} — for example 28.")
    return float(match.group())


def _split_list(raw: object) -> list[str]:
    """Split a comma/semicolon/'and' separated answer into clean items."""
    text = _clean(raw)
    if text.lower() in _SKIP_TOKENS:
        return []
    parts = re.split(r"[,;]|\band\b", text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _parse_name(raw: object) -> str:
    value = _clean(raw)
    if not value:
        raise ValueError("I still need a name — type something like 'Darshan'.")
    if len(value) > 100:
        raise ValueError("That name is over 100 characters. Please use a shorter one.")
    return value


def _parse_age(raw: object) -> int:
    value = _number(raw, "age")
    if value != int(value):
        raise ValueError("Age must be a whole number, for example 28.")
    value = int(value)
    if not 18 <= value <= 100:
        raise ValueError("Age must be between 18 and 100.")
    return value


def _parse_height(raw: object) -> float:
    """Accept centimetres, metres or feet/inches and return centimetres."""
    text = _clean(raw).lower()
    feet_inches = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(?:'|ft|feet)\s*(\d+(?:\.\d+)?)\s*(?:\"|in|inches|'')?",
        text,
    )
    if feet_inches:
        value = float(feet_inches.group(1)) * 30.48 + float(feet_inches.group(2)) * 2.54
    else:
        value = _number(raw, "height")
        # ``1.75 m`` means 175 cm; ``170 cm`` must not be multiplied.
        if "m" in text and "cm" not in text and "mm" not in text:
            value *= 100.0
    if not 50 < value <= 300:
        raise ValueError("Height must be between 50 cm and 300 cm (about 1.6–9.8 ft).")
    return round(value, 1)


def _parse_weight(raw: object) -> float:
    text = _clean(raw).lower()
    value = _number(raw, "weight")
    if "lb" in text:
        value /= 2.20462
    if not 10 < value <= 500:
        raise ValueError("Weight must be between 10 kg and 500 kg (about 22–1100 lb).")
    return round(value, 1)


def _choice_parser(
    options: dict[str, tuple[str, ...]], label: str
) -> Callable[[object], str]:
    """Build a forgiving parser for a fixed set of canonical choices."""
    lookup: dict[str, str] = {}
    for canonical, aliases in options.items():
        for alias in (canonical, *aliases):
            lookup[_key(alias)] = canonical

    valid = ", ".join(options)

    def parse(raw: object) -> str:
        value = lookup.get(_key(raw))
        if value is None:
            raise ValueError(f"Please choose {label}: {valid}.")
        return value

    return parse


_parse_gender = _choice_parser(
    {"male": ("m", "man", "boy"), "female": ("f", "woman", "girl")},
    "male or female",
)

_parse_activity = _choice_parser(
    {
        "sedentary": ("desk job", "inactive", "little movement", "none", "1"),
        "lightly_active": ("lightly", "light", "1-3 days", "1 to 3 days", "2"),
        "moderately_active": ("moderately", "moderate", "3-5 days", "3 to 5 days", "3"),
        "very_active": ("very", "hard exercise", "6-7 days", "6 to 7 days", "4"),
        "extra_active": ("extra", "very hard", "physical job", "twice a day", "5"),
    },
    "an activity level",
)

_parse_goal = _choice_parser(
    {
        "weight_loss": ("weight loss", "lose weight", "lose", "fat loss", "cut", "1"),
        "maintenance": ("maintain", "maintenance", "keep", "stay same", "2"),
        "muscle_gain": ("gain muscle", "muscle gain", "gain", "bulk", "build", "3"),
    },
    "a goal",
)

_parse_diet = _choice_parser(
    {
        "veg": ("vegetarian", "v", "veg only", "plant based", "1"),
        "non-veg": ("non veg", "nonvegetarian", "non vegetarian", "nv", "non", "2"),
    },
    "veg or non-veg",
)


def _parse_allergies(raw: object) -> list[str]:
    cleaned: list[str] = []
    for token in _split_list(raw):
        canonical = canonicalize_allergen(token)
        if canonical is None:  # "none", "no", blank
            continue
        if canonical not in KNOWN_ALLERGENS:
            raise ValueError(
                f"'{token}' isn't a recognised allergen. Choose from: "
                + ", ".join(KNOWN_ALLERGENS)
                + "."
            )
        if canonical not in cleaned:
            cleaned.append(canonical)
    return cleaned


# ── Field definitions ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WizardField:
    """One question in the profile conversation."""

    key: str
    label: str
    question: str
    hint: str
    parse: Callable[[object], Any]
    optional: bool = False
    default: Any = None


WIZARD_FIELDS: tuple[WizardField, ...] = (
    WizardField(
        key="name", label="Name",
        question="First up — what should I call you?",
        hint="Your name",
        parse=_parse_name,
    ),
    WizardField(
        key="age", label="Age",
        question="How old are you?",
        hint="A whole number from 18 to 100",
        parse=_parse_age,
    ),
    WizardField(
        key="gender", label="Gender",
        question="Which should I use for your calorie calculation: male or female?",
        hint="male / female (or m / f)",
        parse=_parse_gender,
    ),
    WizardField(
        key="height_cm", label="Height",
        question="How tall are you?",
        hint="Centimetres (170), metres (1.7 m) or feet/inches (5'7)",
        parse=_parse_height,
    ),
    WizardField(
        key="weight_kg", label="Weight",
        question="What is your current weight?",
        hint="Kilograms (65 kg) or pounds (143 lb)",
        parse=_parse_weight,
    ),
    WizardField(
        key="activity_level", label="Activity level",
        question="How active is a typical week for you?",
        hint="sedentary / lightly_active / moderately_active / very_active / extra_active",
        parse=_parse_activity,
    ),
    WizardField(
        key="fitness_goal", label="Goal",
        question="What is your main goal right now?",
        hint="weight_loss / maintenance / muscle_gain",
        parse=_parse_goal,
    ),
    WizardField(
        key="diet_type", label="Diet",
        question="Do you eat vegetarian or non-vegetarian food?",
        hint="veg / non-veg",
        parse=_parse_diet,
    ),
    WizardField(
        key="allergies", label="Allergies",
        question="Any food allergies I should avoid completely?",
        hint="e.g. dairy, peanuts, gluten — or type 'none'",
        parse=_parse_allergies,
        optional=True,
        default=[],
    ),
    WizardField(
        key="excluded_foods", label="Excluded foods",
        question="Any other foods you dislike enough to leave out?",
        hint="Comma separated, e.g. samosa, sugar — or type 'none'",
        parse=_split_list,
        optional=True,
        default=[],
    ),
    WizardField(
        key="health_conditions", label="Health conditions",
        question="Anything health-wise I should keep in mind? (informational only)",
        hint="e.g. diabetes, hypertension — or type 'none'",
        parse=_split_list,
        optional=True,
        default=None,
    ),
)


# ── State machine ───────────────────────────────────────────────────────────────

def _welcome_history() -> list[dict[str, str]]:
    return [
        {
            "role": "assistant",
            "content": (
                "👋 Hi! I'll build your nutrition profile one question at a time. "
                "Just answer in your own words — I'll check each reply before we "
                "move on. Type **skip** or **none** for anything optional."
            ),
        }
    ]


def _display(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "none"
    if value is None:
        return "none"
    return str(value)


@dataclass
class WizardState:
    """Current position and collected answers of a profile conversation."""

    index: int = 0
    answers: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=_welcome_history)
    last_error: str | None = None

    # ── Introspection ──────────────────────────────────────────────────────────

    @property
    def current_field(self) -> Optional[WizardField]:
        return WIZARD_FIELDS[self.index] if self.index < len(WIZARD_FIELDS) else None

    @property
    def is_complete(self) -> bool:
        return self.index >= len(WIZARD_FIELDS)

    @property
    def progress(self) -> tuple[int, int]:
        return min(self.index, len(WIZARD_FIELDS)), len(WIZARD_FIELDS)

    # ── Transitions ────────────────────────────────────────────────────────────

    def answer(self, raw: object) -> "WizardState":
        """Parse and store one answer; invalid input stays on the same question."""
        spec = self.current_field
        if spec is None:
            return self
        text = _clean(raw)
        transcript = list(self.history) + [
            {"role": "user", "content": text or "(blank)"}
        ]

        try:
            value = spec.parse(text)
        except ValueError as exc:
            message = str(exc)
            return WizardState(
                index=self.index,
                answers=dict(self.answers),
                history=transcript + [
                    {"role": "assistant", "content": f"⚠️ {message} Please try again."}
                ],
                last_error=message,
            )

        answers = dict(self.answers)
        answers[spec.key] = value
        next_field = (
            WIZARD_FIELDS[self.index + 1]
            if self.index + 1 < len(WIZARD_FIELDS)
            else None
        )
        reply = f"✅ Got it — **{spec.label}:** {_display(value)}."
        if next_field:
            reply += f"\n\n{next_field.question}\n_{next_field.hint}_"
        else:
            reply += "\n\n🎉 That's everything I need. Review your answers below."

        return WizardState(
            index=self.index + 1,
            answers=answers,
            history=transcript + [{"role": "assistant", "content": reply}],
            last_error=None,
        )

    def skip(self) -> "WizardState":
        """Accept the default for the current *optional* field."""
        spec = self.current_field
        if spec is None:
            return self
        if not spec.optional:
            raise ValueError(f"'{spec.key}' is required and cannot be skipped.")

        answers = dict(self.answers)
        answers[spec.key] = spec.default
        transcript = list(self.history) + [
            {"role": "user", "content": "skip"},
            {
                "role": "assistant",
                "content": f"⏭️ Skipped **{spec.label}** (using: {_display(spec.default)}).",
            },
        ]
        next_field = (
            WIZARD_FIELDS[self.index + 1]
            if self.index + 1 < len(WIZARD_FIELDS)
            else None
        )
        if next_field:
            transcript[-1]["content"] += (
                f"\n\n{next_field.question}\n_{next_field.hint}_"
            )
        else:
            transcript[-1]["content"] += (
                "\n\n🎉 That's everything I need. Review your answers below."
            )
        return WizardState(
            index=self.index + 1,
            answers=answers,
            history=transcript,
            last_error=None,
        )

    def restart(self) -> "WizardState":
        """Start a fresh conversation."""
        return WizardState()

    # ── Output ─────────────────────────────────────────────────────────────────

    def build_profile(self) -> UserProfile:
        """Final validation target — every answer goes through Pydantic here."""
        if not self.is_complete:
            remaining = len(WIZARD_FIELDS) - self.index
            raise ValueError(
                f"Profile is incomplete — {remaining} answer(s) are still needed."
            )
        return UserProfile(**self.answers)

    def profile_data(self) -> dict[str, Any]:
        return self.build_profile().model_dump()

    def summary_lines(self) -> list[str]:
        lines = []
        for spec in WIZARD_FIELDS:
            if spec.key in self.answers:
                lines.append(f"- **{spec.label}:** {_display(self.answers[spec.key])}")
        return lines

    # ── Session-state persistence ──────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "answers": dict(self.answers),
            "history": [dict(message) for message in self.history],
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "WizardState":
        if not data:
            return cls()
        return cls(
            index=int(data.get("index", 0)),
            answers=dict(data.get("answers") or {}),
            history=[dict(message) for message in (data.get("history") or _welcome_history())],
            last_error=data.get("last_error"),
        )


def build_from_answers(answers: Iterable[object]) -> UserProfile:
    """Drive the wizard from an ordered list of answers (handy for tests/CLI)."""
    state = WizardState()
    for answer in answers:
        if state.is_complete:
            break
        state = state.answer(answer)
    return state.build_profile()


__all__ = [
    "KNOWN_ALLERGENS",
    "WIZARD_FIELDS",
    "WizardField",
    "WizardState",
    "build_from_answers",
]
