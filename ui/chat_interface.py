"""
ui/chat_interface.py
--------------------
Page 5: Modern AI Nutritionist Chat Assistant powered by Gemini, LangGraph, and RAG.
Context-aware of user profile, allergies, and generated meal plan.
"""

from typing import Any, Optional
import streamlit as st
from langchain_core.messages import HumanMessage
from agent.graph import app_graph


SUGGESTED_PROMPTS = [
    "Why did you recommend this meal?",
    "Suggest an alternative for lunch.",
    "Replace rice with another food.",
    "Give me a high-protein vegetarian breakfast.",
    "Explain my daily nutritional breakdown.",
    "What are the nutritional benefits of millets?",
]


def _get_chat_history() -> list[dict[str, str]]:
    """Retrieve chat history safely across streamlit contexts."""
    history = getattr(st.session_state, "chat_history", None)
    if history is None:
        default_history = [
            {
                "role": "assistant",
                "content": (
                    "Namaste! I am your AI Nutritionist. I have analyzed your biometric profile, targets, and meal plan. "
                    "Feel free to ask why specific meals were chosen, request recipe alternatives, or ask questions about Indian food nutrition!"
                ),
            }
        ]
        try:
            st.session_state["chat_history"] = default_history
        except Exception:
            pass
        return default_history
    return history


def render_chat_interface(
    thread_id: str,
    user_profile: Optional[dict[str, Any]] = None,
    nutrition_targets: Optional[dict[str, Any]] = None,
    weekly_plan: Optional[dict[str, Any]] = None,
) -> None:
    """Render the AI Nutritionist chat interface with session conversation memory."""
    st.markdown("### 💬 AI Nutritionist Consultation")
    st.caption("Ask questions about your meal plan, request substitutions, or ask conceptual nutrition questions backed by ICMR-NIN science.")

    # Context notice badge
    p_name = user_profile.get("name", "User") if user_profile else "Guest"
    p_diet = user_profile.get("diet_type", "veg").upper() if user_profile else "VEG"
    allergies = user_profile.get("allergies", []) if user_profile else []
    allergy_str = ", ".join(allergies) if allergies else "None"

    st.markdown(
        f"""
        <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 0.6rem 0.9rem; font-size: 0.85rem; color: #166534; margin-bottom: 1rem;">
            👤 <strong>Active Context:</strong> {p_name} | Diet: <strong>{p_diet}</strong> | Allergen Guard: <strong>{allergy_str}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chat_history = _get_chat_history()

    # Quick prompt pills
    st.markdown("**Suggested questions:**")
    q_cols = st.columns(3)
    selected_quick_prompt = None
    for idx, prompt in enumerate(SUGGESTED_PROMPTS):
        with q_cols[idx % 3]:
            if st.button(prompt, key=f"quick_prompt_{idx}", use_container_width=True):
                selected_quick_prompt = prompt

    st.divider()

    # Render previous messages
    for msg in chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask a question (e.g. 'Why did you recommend this meal?', 'Suggest an alternative for lunch')...")
    prompt_to_send = selected_quick_prompt or user_input

    if prompt_to_send:
        # Display user message
        chat_history.append({"role": "user", "content": prompt_to_send})
        try:
            st.session_state["chat_history"] = chat_history
        except Exception:
            pass

        with st.chat_message("user"):
            st.markdown(prompt_to_send)

        # Send to LangGraph Agent
        with st.chat_message("assistant"):
            with st.spinner("AI Nutritionist is analyzing nutrition science and guidelines..."):
                try:
                    config = {"configurable": {"thread_id": thread_id}}
                    input_state = {
                        "messages": [HumanMessage(content=prompt_to_send)],
                        "user_profile": user_profile,
                        "nutrition_targets": nutrition_targets,
                    }
                    result = app_graph.invoke(input_state, config=config)

                    response_text = result.get("final_response")
                    if not response_text:
                        msgs = result.get("messages", [])
                        response_text = msgs[-1].content if msgs else "I could not generate a response."

                    st.markdown(response_text)
                    chat_history.append({"role": "assistant", "content": response_text})
                    try:
                        st.session_state["chat_history"] = chat_history
                    except Exception:
                        pass
                except Exception as e:
                    err_msg = f"Error during consultation: {e}"
                    st.error(err_msg)
                    chat_history.append({"role": "assistant", "content": err_msg})
