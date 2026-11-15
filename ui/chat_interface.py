"""
ui/chat_interface.py
--------------------
Interactive Streamlit chat assistant powered by Gemini and LangGraph.
Allows multi-turn Q&A, dietary questions, and on-the-fly meal adjustments.
"""

from typing import Any, Optional
import streamlit as st
from langchain_core.messages import HumanMessage
from agent.graph import app_graph, extract_meal_plan_json


SUGGESTED_PROMPTS = [
    "Suggest an alternative to paneer for lunch.",
    "Give me another healthy vegetarian breakfast option.",
    "Why did you recommend this food combination?",
    "How can I increase the protein content of my dinner?",
]


def _get_chat_history() -> list[dict[str, str]]:
    """Retrieve chat history safely across streamlit and non-interactive contexts."""
    history = getattr(st.session_state, "chat_history", None)
    if history is None:
        default_history = [
            {
                "role": "assistant",
                "content": (
                    "Namaste! I am your AI Nutritionist. I have analyzed your profile and targets. "
                    "Feel free to ask me to swap any meal, suggest alternatives, or explain the nutritional benefits!"
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
) -> None:
    """Render the AI Nutritionist chat interface with session conversation memory."""
    st.markdown("### 💬 Chat with your AI Nutritionist")
    st.caption("Ask questions about your meal plan, request substitutions, or ask for dietary tips.")

    chat_history = _get_chat_history()

    # Quick prompt pills
    st.markdown("**Quick questions:**")
    q_cols = st.columns(len(SUGGESTED_PROMPTS))
    selected_quick_prompt = None
    for idx, prompt in enumerate(SUGGESTED_PROMPTS):
        with q_cols[idx]:
            if st.button(prompt, key=f"quick_prompt_{idx}", use_container_width=True):
                selected_quick_prompt = prompt

    # Render previous messages
    for msg in chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask a question (e.g. 'Substitute brown rice for basmati rice')...")
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
            with st.spinner("AI Nutritionist is thinking..."):
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
                        # Extract last AIMessage if final_response not set
                        msgs = result.get("messages", [])
                        response_text = msgs[-1].content if msgs else "I could not generate a response."

                    st.markdown(response_text)
                    chat_history.append({"role": "assistant", "content": response_text})
                    try:
                        st.session_state["chat_history"] = chat_history
                    except Exception:
                        pass

                    # If the assistant generated a new meal plan in chat, offer to update the dashboard
                    new_plan = extract_meal_plan_json(response_text)
                    if new_plan and result.get("meal_plan"):
                        try:
                            st.session_state["meal_plan"] = result.get("meal_plan")
                            if result.get("validation_result"):
                                st.session_state["validation_result"] = result.get("validation_result")
                            st.toast("🎉 Meal plan updated based on your conversation!")
                        except Exception:
                            pass

                except Exception as exc:
                    err_msg = f"Sorry, I encountered an error communicating with the agent: {str(exc)}"
                    st.error(err_msg)
                    chat_history.append({"role": "assistant", "content": err_msg})
                    try:
                        st.session_state["chat_history"] = chat_history
                    except Exception:
                        pass
