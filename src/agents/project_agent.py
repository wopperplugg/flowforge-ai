from langchain.agents import create_agent

from src.agents.model import create_chat_model


def create_project_agent(*, search_tool):
    model = create_chat_model()

    return create_agent(
        model=model,
        tools=[search_tool],
        system_prompt=(
            "You are the FlowForge project assistant. "
            "Use the available tools when the user asks about project-specific "
            "tasks, implementation details, project state, or project knowledge. "
            "Do not invent project facts. "
            "If the tools do not provide enough information, say so explicitly."
        ),
    )