import pytest

from src.ingestion.chunker import TextChunker


def test_text_chunker_normalizes_and_splits_with_overlap() -> None:
    chunker = TextChunker(
        chunk_size=5,
        chunk_overlap=2,
    )

    chunks = chunker.split("  abc   def  ")

    assert [(chunk.index, chunk.content) for chunk in chunks] == [
        (0, "abc d"),
        (1, "def"),
    ]


def test_text_chunker_returns_empty_for_blank_text() -> None:
    chunker = TextChunker()

    assert chunker.split(" \n\t ") == []


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap", "message"),
    [
        (0, 0, "chunk_size must be positive"),
        (10, -1, "chunk_overlap cannot be negative"),
        (10, 10, "chunk_overlap must be less than chunk_size"),
    ],
)
def test_text_chunker_validates_configuration(
    chunk_size: int,
    chunk_overlap: int,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
