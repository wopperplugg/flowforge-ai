from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    content: str


class TextChunker:
    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def split(
        self,
        text: str,
    ) -> list[TextChunk]:
        normalized = " ".join(text.split())

        if not normalized:
            return []

        chunks: list[TextChunk] = []

        start = 0
        index = 0

        while start < len(normalized):
            end = min(
                start + self._chunk_size,
                len(normalized),
            )

            content = normalized[start:end].strip()

            if content:
                chunks.append(
                    TextChunk(
                        index=index,
                        content=content,
                    )
                )

                index += 1

            if end >= len(normalized):
                break

            start = end - self._chunk_overlap

        return chunks
