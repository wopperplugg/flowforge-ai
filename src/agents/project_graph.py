from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agents.model import create_chat_model

SYSTEM_PROMPT = """
You are the FlowForge project assistant.

Use the available tools when the user asks about project-specific
tasks, implementation details, project state, or project knowledge.

Do not invent project facts.

If the available project information is insufficient,
say so explicitly.
"""


def create_project_graph(*, search_tool: Any) -> Any:
    model = create_chat_model()

    tools = [search_tool]

    model_with_tools = model.bind_tools(tools)

    async def call_model(state: MessagesState) -> dict[str, Any]:
        response = await model_with_tools.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                *state["messages"],
            ]
        )

        return {
            "messages": [response],
        }

    tool_node = ToolNode(tools)

    builder = StateGraph(MessagesState)

    builder.add_node(
        "agent",
        call_model,
    )

    builder.add_node(
        "tools",
        tool_node,
    )

    builder.add_edge(
        START,
        "agent",
    )

    builder.add_conditional_edges(
        "agent",
        tools_condition,
    )

    builder.add_edge(
        "tools",
        "agent",
    )

    return builder.compile()
