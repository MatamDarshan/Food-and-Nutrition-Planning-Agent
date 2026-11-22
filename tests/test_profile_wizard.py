"""
tests/test_profile_wizard.py
----------------------------
Hermetic tests for the optional conversational profile wizard.

The state-machine tests need no browser; one AppTest smoke test confirms the
chat UI is wired into the profile page while the default form stays untouched.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.profile_wizard import (
    WIZARD_FIELDS,
    WizardState,
    build_from_answers,
)
from core.user_profile import UserProfile

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP_FILE = str(Path(__file__).resolve().parents[1] / "app.py")

FULL_ANSWERS = [
    "Darshan", "33", "m", "170 cm", "65 kg",
    "lightly active", "lose weight", "veg",
    "milk, groundnut, cashew", "samosa, sugar", "diabetes",
]


def _walk(answers: list[str]) -> WizardState:
    state = WizardState()
    for answer in answers:
        state = state.answer(answer)
    return state


# ── State machine ───────────────────────────────────────────────────────────────

class TestWizardStateMachine:
    def test_wizard_covers_every_profile_field(self):
        assert [spec.key for spec in WIZARD_FIELDS] == list(UserProfile.model_fields)
        assert len({spec.key for spec in WIZARD_FIELDS}) == len(WIZARD_FIELDS)

    def test_full_conversation_builds_valid_profile(self):
        state = _walk(FULL_ANSWERS)
        assert state.is_complete
        assert state.progress == (len(WIZARD_FIELDS), len(WIZARD_FIELDS))

        profile = state.build_profile()
        assert isinstance(profile, UserProfile)
        assert profile.name == "Darshan"
        assert profile.age == 33
        assert profile.gender == "male"
        assert profile.height_cm == 170.0
        assert profile.weight_kg == 65.0
        assert profile.activity_level == "lightly_active"
        assert profile.fitness_goal == "weight_loss"
        assert profile.diet_type == "veg"
        assert profile.allergies == ["dairy", "peanuts", "tree_nuts"]
        assert profile.excluded_foods == ["samosa", "sugar"]
        assert profile.health_conditions == ["diabetes"]
        assert len(state.summary_lines()) == len(WIZARD_FIELDS)

    def test_invalid_answer_retries_same_question(self):
        state = WizardState().answer("Darshan")
        bad = state.answer("not a number")
        assert bad.index == state.index
        assert bad.last_error
        assert any("⚠️" in message["content"] for message in bad.history)

        fixed = bad.answer("28")
        assert fixed.index == state.index + 1
        assert fixed.last_error is None
        assert fixed.answers["age"] == 28

    def test_out_of_range_and_unknown_choices_are_rejected(self):
        cases = [
            (["Darshan", "17"], "between 18 and 100"),
            (["Darshan", "28", "m", "40"], "50 cm"),
            (["Darshan", "28", "m", "170", "900"], "10 kg"),
            (["Darshan", "28", "m", "170", "65", "super active"], "activity level"),
            (["Darshan", "28", "m", "170", "65", "sedentary", "fly"], "goal"),
            (["Darshan", "28", "m", "170", "65", "sedentary", "maintain", "paleo"], "veg or non-veg"),
        ]
        for answers, expected in cases:
            state = _walk(answers)
            assert state.last_error and expected in state.last_error, (answers, state.last_error)

    def test_alias_parsing_for_choices_and_units(self):
        profile = build_from_answers(
            ["Asha", "40", "f", "1.65 m", "143 lb", "moderate", "maintain", "non vegetarian"]
            + ["none", "none", "none"]
        )
        assert profile.gender == "female"
        assert profile.height_cm == 165.0
        assert profile.weight_kg == pytest.approx(64.9, abs=0.1)
        assert profile.activity_level == "moderately_active"
        assert profile.fitness_goal == "maintenance"
        assert profile.diet_type == "non-veg"

        feet = build_from_answers(
            ["Arjun", "30", "male", "5'7", "70", "1", "2", "1"] + ["skip"] * 3
        )
        assert feet.height_cm == pytest.approx(170.2, abs=0.1)

    def test_allergen_synonyms_and_unknown_rejection(self):
        state = _walk(FULL_ANSWERS[:8] + ["durian"])
        assert "recognised allergen" in state.last_error
        assert "allergies" not in state.answers

        state = state.answer("gluten, egg, soy, gluten")
        assert state.answers["allergies"] == ["gluten", "eggs", "soy"]

    def test_optional_fields_can_be_skipped_or_answered_none(self):
        state = _walk(FULL_ANSWERS[:8])
        for _ in range(3):
            state = state.skip()
            assert state.last_error is None
        profile = state.build_profile()
        assert profile.allergies == []
        assert profile.excluded_foods == []
        assert profile.health_conditions is None

        typed_none = _walk(FULL_ANSWERS[:8] + ["none", "none", "none"])
        assert typed_none.build_profile().health_conditions == []

    def test_skip_rejected_for_required_field(self):
        with pytest.raises(ValueError, match="required"):
            WizardState().skip()

    def test_incomplete_profile_raises(self):
        state = WizardState().answer("Darshan")
        with pytest.raises(ValueError, match="incomplete"):
            state.build_profile()

    def test_final_pydantic_validation_still_applies(self):
        """The wizard cannot bypass UserProfile even if its answers are poisoned."""
        state = _walk(FULL_ANSWERS)
        poisoned = dict(state.answers)
        poisoned["age"] = 12
        forged = WizardState(index=state.index, answers=poisoned)
        with pytest.raises(ValidationError):
            forged.build_profile()

    def test_state_roundtrip_and_restart(self):
        state = _walk(FULL_ANSWERS[:4])
        restored = WizardState.from_dict(state.to_dict())
        assert restored.index == state.index
        assert restored.answers == state.answers
        assert restored.history == state.history
        for answer in FULL_ANSWERS[4:]:
            restored = restored.answer(answer)
        assert restored.build_profile().name == "Darshan"

        fresh = state.restart()
        assert fresh.index == 0
        assert fresh.answers == {}
        assert WizardState.from_dict(None).index == 0

    def test_build_from_answers_helper(self):
        profile = build_from_answers(FULL_ANSWERS)
        assert profile.name == "Darshan"
        assert profile.allergies == ["dairy", "peanuts", "tree_nuts"]


# ── Streamlit integration ───────────────────────────────────────────────────────

def test_conversational_wizard_creates_a_profile():
    app = AppTest.from_file(APP_FILE, default_timeout=300)
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]

    next(btn for btn in app.button if "New profile" in btn.label).click()
    app.run()
    next(radio for radio in app.radio if radio.label == "Profile input mode").set_value(
        "Chat wizard"
    )
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    assert any("Build your profile" in block.value for block in app.markdown)

    # An invalid answer must keep the wizard on the same question.
    app.chat_input[0].set_value("Wizard User").run()
    app.chat_input[0].set_value("not a number").run()
    assert any("⚠️" in message.value for message in app.markdown)
    assert app.session_state["profile_wizard_state"].index == 1

    app.chat_input[0].set_value("33").run()
    for answer in ["f", "165 cm", "58 kg", "moderate", "maintain", "veg"]:
        app.chat_input[0].set_value(answer).run()
        assert not app.exception, [exc.value for exc in app.exception]

    # Allergies are optional — use the Skip button rather than typing.
    next(btn for btn in app.button if btn.label == "⏭️ Skip this question").click()
    app.run()
    for answer in ["samosa", "none"]:
        app.chat_input[0].set_value(answer).run()

    assert app.session_state["profile_wizard_state"].is_complete
    next(btn for btn in app.button if "Create plan with this profile" in btn.label).click()
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    assert "Wizard User" in app.session_state["users"]
    assert app.session_state["user_profile"]["age"] == 33
    assert app.session_state["user_profile"]["allergies"] == []
    assert app.session_state["active_nav"] == "🍽️ Today"
    assert app.session_state["weekly_plan"]["days"]

    # The wizard resets itself so the next conversation starts at question 1.
    assert app.session_state.get("profile_wizard_state") is None
