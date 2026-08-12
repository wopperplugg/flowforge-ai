import uuid
from typing import Any

import httpx

from src.flowforge_api.schemas import (
    Page,
    ProjectResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)


class FlowForgeAPIError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class FlowForgeAPIUnavailableError(RuntimeError):
    pass


class FlowForgeAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds

    async def get_project(
        self,
        project_id: uuid.UUID,
    ) -> ProjectResponse:
        payload = await self._request(
            "GET",
            f"/api/v1/projects/{project_id}",
        )
        return ProjectResponse.model_validate(payload)

    async def list_tasks(
        self,
        project_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Page[TaskResponse]:
        payload = await self._request(
            "GET",
            f"/api/v1/projects/{project_id}/tasks",
            params={
                "limit": limit,
                "offset": offset,
            },
        )
        return Page[TaskResponse].model_validate(payload)

    async def get_task(
        self,
        task_id: uuid.UUID,
    ) -> TaskResponse:
        payload = await self._request(
            "GET",
            f"/api/v1/tasks/{task_id}",
        )
        return TaskResponse.model_validate(payload)

    async def create_task(
        self,
        project_id: uuid.UUID,
        payload: TaskCreate,
    ) -> TaskResponse:
        response_payload = await self._request(
            "POST",
            f"/api/v1/projects/{project_id}/tasks",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        return TaskResponse.model_validate(response_payload)

    async def update_task(
        self,
        task_id: uuid.UUID,
        payload: TaskUpdate,
    ) -> TaskResponse:
        response_payload = await self._request(
            "PATCH",
            f"/api/v1/tasks/{task_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        return TaskResponse.model_validate(response_payload)

    async def delete_task(
        self,
        *,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> None:
        await self._request(
            "DELETE",
            f"/api/v1/projects/{project_id}/tasks/{task_id}",
        )

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                },
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise FlowForgeAPIUnavailableError(
                "FlowForge API request timed out"
            ) from exc
        except httpx.TransportError as exc:
            raise FlowForgeAPIUnavailableError("FlowForge API is unavailable") from exc

        if response.is_error:
            raise FlowForgeAPIError(
                status_code=response.status_code,
                message=_error_message(response),
            )

        if response.status_code == 204 or not response.content:
            return None

        return response.json()


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "FlowForge API request failed"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message

        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail

    return "FlowForge API request failed"
