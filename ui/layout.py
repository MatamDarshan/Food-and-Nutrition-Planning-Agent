"""
ui/layout.py
------------
Page shells, hero headers and the shared sidebar for the AI Nutrition Planner.

These helpers keep page modules focused on content while giving every screen a
consistent, premium health-tech frame.  They contain no business logic beyond
navigation/state plumbing that used to live inline in ``app.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import Any, Optional

import streamlit as st

from ui.components import render_badges, section_header


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: Optional[str],
    icon: Optional[str] = None,
    badges: Optional[Sequence[Mapping[str, str]]] = None,
    level: int = 2,
) -> None:
    """Render a consistent inner-page heading and optional badges."""
    section_header(title, subtitle=subtitle, icon=icon, level=level)
    if badges:
        render_badges(badges)


def render_today_hero(
    user_name: str,
    badges: Sequence[Mapping[str, str]],
    subtitle: str = "Your personalised nutrition plan for today",
    eyebrow: str = "AI Nutrition Planner · Daily dashboard",
) -> None:
    """Render the large welcome banner used as the default-page header."""
    safe_name = escape(str(user_name or "there"))
    _html(
        f'<div class="np-hero">'
        f'<div class="np-hero-eyebrow">{escape(eyebrow)}</div>'
        f"<h1>👋 Good day, {safe_name}!</h1>"
        f"<p>{escape(subtitle)}</p>"
        f"</div>"
    )
    render_badges(badges)


def render_chat_hero(title: str, subtitle: str) -> None:
    """Render the friendly chat-page hero."""
    _html(
        f'<div class="np-hero" style="background:linear-gradient(115deg,#FFFFFF 0%,'
        f'#EAF7F2 55%,#FFF1E6 100%);">'
        f'<div class="np-hero-eyebrow">AI nutritionist</div>'
        f"<h1>🤖 {escape(title)}</h1>"
        f"<p>{escape(subtitle)}</p></div>"
    )


def render_sidebar(
    pages: Sequence[str],
    current_name: str,
    users: Mapping[str, Any],
    api_key: str,
    model_name: str,
    on_new_profile: Callable[[], None],
) -> None:
    """Render the branded sidebar with profile, navigation and engine state.

    Widget labels and keys are intentionally stable: AppTest and existing users
    depend on ``Active profile``, ``Go to`` and the five page options.
    """
    with st.sidebar:
        _html(
            '<div class="np-sidebar-brand">'
            '<div class="np-sidebar-mark">🌿</div>'
            "<div><h2>AI Nutrition Planner</h2>"
            "<p>Personalised Indian meals<br>ICMR-NIN informed</p></div>"
            "</div>"
        )

        saved_names = list(users.keys())
        if saved_names:
            # When the active profile changes programmatically (for example
            # after saving the form), move the keyed selector to match. Without
            # this, its stale value would immediately undo the change.
            if (
                st.session_state.get("_profile_switcher_sync")
                and current_name in saved_names
            ):
                st.session_state.profile_switcher = current_name
                st.session_state._profile_switcher_sync = False

            # Streamlit warns when a keyed widget is created with an explicit
            # default (index=...) while that key already exists in Session
            # State. Pass index only on the widget's very first creation; after
            # that the stored value is the single source of truth.
            switcher_key = "profile_switcher"
            if switcher_key in st.session_state:
                if st.session_state[switcher_key] not in saved_names:
                    st.session_state[switcher_key] = (
                        current_name if current_name in saved_names else saved_names[0]
                    )
                chosen_user = st.selectbox(
                    "Active profile",
                    options=saved_names,
                    label_visibility="collapsed",
                    key=switcher_key,
                )
            else:
                current_index = (
                    saved_names.index(current_name)
                    if current_name in saved_names
                    else 0
                )
                chosen_user = st.selectbox(
                    "Active profile",
                    options=saved_names,
                    index=current_index,
                    label_visibility="collapsed",
                    key=switcher_key,
                )
            if chosen_user != st.session_state.current_user_name:
                st.session_state.current_user_name = chosen_user
                st.session_state._new_user_mode = False
                st.session_state._form_draft_user = None
                st.rerun()
        else:
            st.caption("No profiles yet — create one to get started.")

        st.button(
            "＋ New profile",
            width="stretch",
            on_click=on_new_profile,
            key="sidebar_new_profile",
        )

        st.divider()

        if st.session_state.get("nav_page") not in pages:
            st.session_state.nav_page = st.session_state.get("active_nav", pages[0])
        st.radio(
            "Go to",
            options=list(pages),
            key="nav_page",
            label_visibility="collapsed",
        )
        st.session_state.active_nav = st.session_state.nav_page

        st.divider()

        if api_key:
            safe_model = escape(str(model_name))
            _html(
                '<div class="np-mode-card np-mode-card--live">'
                "🟢 <strong>Mode: Gemini Live</strong>"
                f"<span>Model: {safe_model}</span></div>"
            )
        else:
            _html(
                '<div class="np-mode-card np-mode-card--offline">'
                "💡 <strong>Mode: Offline Fallback</strong>"
                "<span>Deterministic ICMR-NIN planner · Local FAISS RAG</span></div>"
            )


__all__ = [
    "render_chat_hero",
    "render_page_header",
    "render_sidebar",
    "render_today_hero",
]
