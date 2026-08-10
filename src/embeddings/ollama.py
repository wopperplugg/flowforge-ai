from typing import Any, cast

import httpx


def _extract_embeddings(payload: object) -> list[list[float]]:
    if not isinstance(payload, dict):
        raise TypeError("Ollama response must be a JSON object")

    embeddings = payload.get("embeddings")

    if not isinstance(embeddings, list):
        raise TypeError("Ollama response must contain embeddings list")

    return cast(list[list[float]], embeddings)


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=60.0,
        ) as client:
            response = await client.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": text,
                },
            )
            response.raise_for_status()

        embeddings = _extract_embeddings(cast(Any, response.json()))

        return embeddings[0]

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=60.0,
        ) as client:
            response = await client.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": texts,
                },
            )
            response.raise_for_status()

        return _extract_embeddings(cast(Any, response.json()))
