"""
ui/profile_wizard.py
--------------------
Optional conversational alternative to the profile form.

The assistant asks one question at a time, shows each answer in a chat bubble,
and validates through :class:`core.profile_wizard.WizardState`. The finished
profile is returned in exactly the same shape as the form, so ``app.py`` can
build a plan with no special-casing. The classic form remains the default mode.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from core.profile_wizard import WizardState
from ui.components import callout, render_badges, source_note
from ui.layout import render_page_header

WIZARD_STATE_KEY = "profile_wizard_state"
WIZARD_INPUT_KEY = "profile_wizard_answer"


def reset_profile_wizard() -> None:
    """Clear the conversation so the next wizard session starts fresh."""
    st.session_state.pop(WIZARD_STATE_KEY, None)
    st.session_state.pop(WIZARD_INPUT_KEY, None)


def _current_state() -> WizardState:
    stored = st.session_state.get(WIZARD_STATE_KEY)
    if not isinstance(stored, WizardState):
        stored = WizardState()
        st.session_state[WIZARD_STATE_KEY] = stored
    return stored


def _on_submit() -> None:
    """Widget callback: runs *before* the chat input is instantiated."""
    typed = st.session_state.get(WIZARD_INPUT_KEY)
    if not typed:
        return
    st.session_state[WIZARD_STATE_KEY] = _current_state().answer(typed)
    st.session_state[WIZARD_INPUT_KEY] = ""


def _on_skip() -> None:
    """Widget callback for the optional-field skip button."""
    st.session_state[WIZARD_STATE_KEY] = _current_state().skip()


def render_profile_wizard() -> Optional[dict[str, Any]]:
    """Render the chat wizard. Returns validated profile data when submitted."""
    render_page_header(
        "Build your profile",
        subtitle="A short conversation instead of a form. I'll check every answer "
        "before we move on, so nothing gets lost in translation.",
        icon="💬",
        badges=[
            {"label": "One question at a time", "tone": "blue", "icon": "💬"},
            {"label": "Validated as you go", "tone": "green", "icon": "✅"},
        ],
    )

    state = _current_state()
    done, total = state.progress

    progress_col, restart_col = st.columns([5, 1])
    with progress_col:
        st.caption(f"**Step {min(done + 1, total)} of {total}** · {done} answered")
        st.progress(done / total if total else 0.0)
    with restart_col:
        st.button(
            "🔄 Start over",
            key="wizard_restart",
            width="stretch",
            on_click=reset_profile_wizard,
        )

    st.divider()

    for message in state.history:
        role = message.get("role", "assistant")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(message.get("content", ""))

    st.write("")

    # ── Finished: review and submit ──────────────────────────────────────────
    if state.is_complete:
        callout("That's everything! Review your answers, then create your plan.",
                tone="green", icon="🎉")
        section_lines = "\n".join(state.summary_lines())
        st.markdown(section_lines)

        if st.button(
            "🚀 Create plan with this profile",
            type="primary",
            width="stretch",
            key="wizard_create_plan",
        ):
            try:
                profile_data = state.profile_data()
            except Exception as exc:
                st.error(f"One of those answers still needs a fix: {exc}")
                return None
            st.session_state.form_draft = dict(profile_data)
            reset_profile_wizard()
            return profile_data

        source_note(
            "Your answers are validated by the same Pydantic model used by the "
            "form before any targets or meals are calculated."
        )
        return None

    # ── In progress: next question + answer box ──────────────────────────────
    spec = state.current_field
    if spec is None:  # defensive: is_complete should have caught this
        return None

    callout(spec.question, tone="blue", icon="❓")
    st.caption(spec.hint)

    if spec.optional:
        st.button(
            "⏭️ Skip this question",
            key="wizard_skip",
            width="stretch",
            on_click=_on_skip,
        )

    # The callback updates the state machine and clears this widget before it
    # is instantiated, so Streamlit's automatic rerun shows the next question
    # exactly once (no manual st.rerun() and no duplicate submissions).
    st.chat_input(
        "Type your answer here…",
        key=WIZARD_INPUT_KEY,
        on_submit=_on_submit,
    )

    render_badges(
        [
            {"label": "Type 'skip' for optional items", "tone": "amber", "icon": "💡"},
            {"label": "Nothing saved until you create the plan", "tone": "green", "icon": "🔒"},
        ]
    )
    return None


__all__ = [
    "WIZARD_INPUT_KEY",
    "WIZARD_STATE_KEY",
    "render_profile_wizard",
    "reset_profile_wizard",
]
