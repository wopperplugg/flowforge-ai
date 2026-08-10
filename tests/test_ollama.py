import pytest

from src.embeddings.ollama import _extract_embeddings


def test_extract_embeddings_returns_vectors() -> None:
    assert _extract_embeddings(
        {
            "embeddings": [
                [0.1, 0.2],
                [0.3, 0.4],
            ]
        }
    ) == [
        [0.1, 0.2],
        [0.3, 0.4],
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "JSON object"),
        ({}, "embeddings list"),
        ({"embeddings": "bad"}, "embeddings list"),
    ],
)
def test_extract_embeddings_rejects_invalid_payload(
    payload: object,
    message: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=message,
    ):
        _extract_embeddings(payload)
