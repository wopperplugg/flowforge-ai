import asyncio

from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider


async def main() -> None:
    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    vector = await provider.embed_text(
        "JWT authentication and refresh tokens"
    )

    print("dimension:", len(vector))
    print("first values:", vector[:5])


if __name__ == "__main__":
    asyncio.run(main())