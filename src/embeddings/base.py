from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed_text(
        self,
        test: str,
    ) -> list[float]: ...

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]: ...
