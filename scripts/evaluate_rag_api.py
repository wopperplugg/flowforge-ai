import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

DATASET_PATH = Path("evals/rag_questions.jsonl")
RESULTS_PATH = Path("evals/rag_results.jsonl")


async def main() -> None:
    base_url = os.environ.get("FLOWFORGE_AI_BASE_URL", "http://localhost:8001")
    access_token = os.environ["FLOWFORGE_ACCESS_TOKEN"]
    user_id = os.environ["FLOWFORGE_USER_ID"]
    organization_id = os.environ["FLOWFORGE_ORGANIZATION_ID"]
    project_id = os.environ["FLOWFORGE_PROJECT_ID"]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(base_url=base_url, timeout=180) as client:
        with RESULTS_PATH.open("w", encoding="utf-8") as output:
            for item in _load_dataset():
                response = await client.post(
                    "/v1/assistant/query",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-User-Id": user_id,
                        "X-Organization-Id": organization_id,
                    },
                    json={
                        "project_id": project_id,
                        "question": item["question"],
                        "thread_id": f"eval-{uuid.uuid4()}",
                    },
                )
                output.write(
                    json.dumps(
                        {
                            "id": item["id"],
                            "question": item["question"],
                            "status_code": response.status_code,
                            "response": response.json(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )


def _load_dataset() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    asyncio.run(main())
