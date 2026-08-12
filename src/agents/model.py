from langchain_ollama import ChatOllama

from src.config import settings


def create_chat_model() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        temperature=0,
    )