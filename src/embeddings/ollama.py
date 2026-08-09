import httpx


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
                json={"model": self._model,
                      "input": text,
                    },
            )
            response.raise_for_status()

        return response.json()["embeddings"][0]

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

        return response.json()["embeddings"]