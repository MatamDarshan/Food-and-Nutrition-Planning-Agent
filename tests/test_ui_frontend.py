"""
tests/test_ui_frontend.py
-------------------------
Frontend smoke tests built on Streamlit's official AppTest harness.

They guard the user-facing problems seen in the screen recording:
1. the app opens on a single clear "Today" page with calories and a timetable;
2. no timetable cell dumps a 150-character portion string;
3. metric values stay short enough to display without "2768 ...";
4. the week page shows one day at a time;
5. a new user can be created from the profile form;
6. the AI chat is a separate page with short suggestion chips.

Note: Streamlit form widgets only deliver their values together with the form
submit button, so values must be set and the submit clicked before the next
``at.run()``.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_FILE = str(Path(__file__).resolve().parents[1] / "app.py")

PAGE_TODAY = "🍽️ Today"
PAGE_WEEK = "📅 My week"
PAGE_PROFILE = "👤 My profile"
PAGE_FOOD_DB = "🥗 Food data"
PAGE_CHAT = "🤖 Ask AI"

ALL_PAGES = [PAGE_TODAY, PAGE_WEEK, PAGE_PROFILE, PAGE_FOOD_DB, PAGE_CHAT]

CHIP_LABELS = {
    "Breakfast",
    "Lunch swap",
    "Snacks",
    "Protein dinner",
    "My numbers",
    "ICMR-NIN facts",
}


def _boot() -> AppTest:
    """Start a fresh app instance and let the demo plan bootstrap run."""
    app = AppTest.from_file(APP_FILE, default_timeout=300)
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    return app


def _nav(app: AppTest, page: str) -> None:
    """Click a sidebar page once, the way a user would."""
    next(radio for radio in app.radio if radio.label == "Go to").set_value(page)
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]


def test_today_week_and_chat_pages_are_clear():
    app = _boot()

    # Opens directly on the single Today page.
    assert app.session_state["active_nav"] == PAGE_TODAY
    assert app.session_state["weekly_plan"]["days"]
    assert app.tabs == []  # the old 8-tab wall is gone

    # Calories and the timetable are present.
    labels = [metric.label for metric in app.metric]
    assert "Calories (kcal)" in labels
    assert "Protein (g)" in labels
    assert any("Timetable" in block.value for block in app.markdown)
    assert any("8:00" in frame.value.to_string() for frame in app.dataframe)

    # Every metric value is short enough to render; no ellipsis placeholders.
    for metric in app.metric:
        assert len(metric.value) <= 12, (metric.label, metric.value)
        assert not metric.value.rstrip().endswith("...")
        assert not metric.value.rstrip().endswith("…")

    # Timetable cells are cleaned up: names only, no "(approx. 100-150g)" walls.
    for frame in app.dataframe:
        text = frame.value.astype(str).to_string()
        assert "approx." not in text
        assert len(text.split("\n")[0]) < 400

    # Each meal exposes swap options.
    assert any("Swap ideas" in block.value for block in app.caption)
    assert len([b for b in app.button if b.label == "🔄 Rebuild plan"]) == 1

    # Week page: one compact table, then a single chosen day.
    _nav(app, PAGE_WEEK)
    assert app.session_state["active_nav"] == PAGE_WEEK
    assert any(select.label == "Show a day" for select in app.selectbox)
    assert any("My week" in block.value for block in app.markdown)

    # Chat is its own page with short chips and a working input. Each page
    # change must take effect on the first click, not the second.
    _nav(app, PAGE_CHAT)
    assert app.session_state["active_nav"] == PAGE_CHAT
    assert len(app.chat_input) == 1
    chip_labels = {b.label for b in app.button} & CHIP_LABELS
    assert chip_labels == CHIP_LABELS
    assert any("Knows:" in caption.value for caption in app.caption)


def test_add_new_user_from_profile_form():
    app = _boot()
    next(btn for btn in app.button if "New profile" in btn.label).click()
    app.run()
    assert app.session_state["active_nav"] == PAGE_PROFILE

    next(field for field in app.text_input if field.label.startswith("Name")).set_value(
        "Test User"
    )
    for number in app.number_input:
        if number.label.startswith("Age"):
            number.set_value(33)
    next(btn for btn in app.button if "Save profile" in btn.label).click()
    app.run()

    assert not app.exception, [exc.value for exc in app.exception]
    assert app.error == []
    assert "Test User" in app.session_state["users"]
    assert app.session_state["current_user_name"] == "Test User"
    assert app.session_state["user_profile"]["age"] == 33
    assert app.session_state["active_nav"] == PAGE_TODAY
    assert app.session_state["weekly_plan"]["days"]

    # Moving between pages keeps working after the form has been used.
    _nav(app, PAGE_PROFILE)
    assert app.session_state["active_nav"] == PAGE_PROFILE
    assert (
        next(field for field in app.text_input if field.label.startswith("Name")).value
        == "Test User"
    )
    _nav(app, PAGE_CHAT)
    assert app.session_state["active_nav"] == PAGE_CHAT


def test_switching_profiles_refreshes_the_form():
    """Switching the active profile must refresh the form fields.

    Streamlit keeps widget values in session state by key, so the form widgets
    are re-created from the profile token. Without that, the form kept showing
    the previously selected user's details.
    """
    app = _boot()
    next(btn for btn in app.button if "New profile" in btn.label).click()
    app.run()

    next(field for field in app.text_input if field.label.startswith("Name")).set_value(
        "Second User"
    )
    next(btn for btn in app.button if "Save profile" in btn.label).click()
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]

    _nav(app, PAGE_PROFILE)
    assert (
        next(field for field in app.text_input if field.label.startswith("Name")).value
        == "Second User"
    )

    # Switch back to the demo profile from the sidebar.
    active = next(select for select in app.selectbox if select.label == "Active profile")
    active.set_value("Arjun")
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    assert app.session_state["current_user_name"] == "Arjun"
    assert app.session_state["user_profile"]["name"] == "Arjun"
    assert (
        next(field for field in app.text_input if field.label.startswith("Name")).value
        == "Arjun"
    ), "Profile form still shows the previous user after switching."


def _markdown_contains(app: AppTest, needle: str) -> bool:
    """Return whether any markdown block contains ``needle``."""
    return any(needle in block.value for block in app.markdown)


def test_all_five_pages_render():
    """Every sidebar destination renders without an exception."""
    app = _boot()
    radio = next(r for r in app.radio if r.label == "Go to")
    assert list(radio.options) == ALL_PAGES

    for page in ALL_PAGES:
        # Re-fetch the radio after each run; element handles are per-run.
        _nav(app, page)
        assert app.session_state["active_nav"] == page

    # Page-specific checkpoints.
    _nav(app, PAGE_TODAY)
    assert any("Timetable" in block.value for block in app.markdown)
    _nav(app, PAGE_WEEK)
    assert any(s.label == "Show a day" for s in app.selectbox)
    _nav(app, PAGE_PROFILE)
    assert any("Save profile" in b.label for b in app.button)
    _nav(app, PAGE_FOOD_DB)
    assert any(s.label == "Dietary Category" for s in app.selectbox)
    _nav(app, PAGE_CHAT)
    assert len(app.chat_input) == 1


def test_preset_fills_and_saves_the_form():
    """A quick-start preset must populate every field, then save cleanly."""
    app = _boot()
    _nav(app, PAGE_PROFILE)

    preset = next(b for b in app.button if b.label.startswith("Priya (veg, maintain)"))
    preset.click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]

    name = next(f for f in app.text_input if f.label.startswith("Name"))
    assert name.value == "Priya"
    age = next(n for n in app.number_input if n.label.startswith("Age"))
    assert age.value == 25
    excluded = next(
        f for f in app.text_input if f.label.startswith("Other foods you dislike")
    )
    assert excluded.value == ""

    save = next(b for b in app.button if "Save profile" in b.label)
    save.click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert "Priya" in app.session_state["users"]
    assert app.session_state["current_user_name"] == "Priya"
    assert app.session_state["active_nav"] == PAGE_TODAY


def test_food_database_search_and_filtering():
    """Search and diet filter narrow the ICMR-NIN food table."""
    app = _boot()
    _nav(app, PAGE_FOOD_DB)
    assert not app.exception, [e.value for e in app.exception]

    def showing_count() -> int:
        badge = next(
            block.value
            for block in app.markdown
            if "Showing" in block.value and "foods" in block.value
        )
        return int(badge.split("Showing")[1].split("of")[0].strip())

    total = showing_count()
    assert total > 0

    search = next(t for t in app.text_input if t.label == "Search food by name")
    search.set_value("idli")
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    searched = showing_count()
    assert 0 < searched < total
    food_names = app.dataframe[0].value["Food Name"].astype(str).str.lower()
    assert food_names.str.contains("idli").all()

    diet = next(s for s in app.selectbox if s.label == "Dietary Category")
    diet.set_value("Non-Vegetarian")
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert showing_count() == 0  # idli is vegetarian

    # The inspector still offers the full catalogue when a filter is empty.
    inspector = next(
        s for s in app.selectbox if s.label == "Select a Food Item to Inspect"
    )
    assert inspector.options


def test_chat_submission_renders_rag_and_rejects_irrelevant_query():
    """Chat turns preserve RAG formatting and the irrelevant-query notice."""
    app = _boot()
    _nav(app, PAGE_CHAT)

    # Offline fallback is active because GOOGLE_API_KEY is empty.
    assert _markdown_contains(app, "Offline Fallback")

    relevant = "What are the nutritional benefits of millets?"
    app.chat_input[0].set_value(relevant).run()
    assert not app.exception, [e.value for e in app.exception]
    chat_text = "\n".join(msg.value for msg in app.markdown)
    assert "**Answer (from the ICMR-NIN knowledge base)**" in chat_text
    assert "**Supporting excerpts**" in chat_text
    assert "**Sources**" in chat_text
    assert "Vector Distance" in chat_text
    assert relevant in chat_text

    irrelevant = "How do I mine bitcoin with a GPU?"
    app.chat_input[0].set_value(irrelevant).run()
    assert not app.exception, [e.value for e in app.exception]
    chat_text = "\n".join(msg.value for msg in app.markdown)
    assert "No relevant document sections were found in the ICMR-NIN knowledge base" in chat_text
    assert irrelevant in chat_text

    # Chat history is scoped to the chat thread, separate from plan state.
    history_keys = [
        key for key in app.session_state.keys() if str(key).startswith("chat_history_")
    ]
    assert len(history_keys) == 1
    assert len(app.session_state[history_keys[0]]) == 5  # welcome + 2 turns x 2


def test_rag_chip_and_my_numbers_chip_answer_correctly():
    """The RAG chip shows citations; 'My numbers' shows the user's real targets."""
    app = _boot()
    _nav(app, PAGE_CHAT)

    # The dedicated knowledge chip must reach the RAG branch and render the
    # full cited answer/excerpts/sources/distance trail.
    next(btn for btn in app.button if btn.label == "ICMR-NIN facts").click()
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    chat_text = "\n".join(msg.value for msg in app.markdown)
    assert "**Answer (from the ICMR-NIN knowledge base)**" in chat_text
    assert "**Supporting excerpts**" in chat_text
    assert "**Sources**" in chat_text
    assert "Vector Distance" in chat_text

    # "My numbers" must answer with the computed targets rather than an
    # unrelated FAISS chunk about dietary fibre.
    next(btn for btn in app.button if btn.label == "🧹 Clear chat").click()
    app.run()
    next(btn for btn in app.button if btn.label == "My numbers").click()
    app.run()
    assert not app.exception, [exc.value for exc in app.exception]
    chat_text = "\n".join(msg.value for msg in app.markdown)
    assert "Daily Energy Target:" in chat_text
    assert "Protein Goal:" in chat_text
    assert "**Answer (from the ICMR-NIN knowledge base)**" not in chat_text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
