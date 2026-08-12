import asyncio

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.model import create_chat_model


async def main() -> None:
    model = create_chat_model()

    messages = [
        SystemMessage(
            content=(
                "You are an AI assistant for FlowForge, "
                "a project management application."
            )
        ),
        HumanMessage(content="What can you help a project manager with?"),
    ]

    response = await model.ainvoke(messages)

    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
