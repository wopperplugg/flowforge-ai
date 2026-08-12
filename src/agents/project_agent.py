from typing import Any

from langchain.agents import create_agent

from src.agents.model import create_chat_model


def create_project_agent(*, tools: list[Any]) -> Any:
    model = create_chat_model()

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=(
            "You are the FlowForge project assistant. "
            "Use the available tools when the user asks about project-specific "
            "tasks, implementation details, project state, or project knowledge. "
            "Read tools may be used automatically. "
            "Write tools may be used only when they report that external human "
            "approval has been granted. "
            "Do not invent project facts. "
            "If the tools do not provide enough information, say so explicitly."
        ),
    )
