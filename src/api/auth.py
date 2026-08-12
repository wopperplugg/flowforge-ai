import uuid
from typing import Annotated

from fastapi import Header, HTTPException, status
from pydantic import BaseModel


class AuthenticatedContext(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    access_token: str


async def get_authenticated_context(
    x_user_id: Annotated[
        uuid.UUID | None,
        Header(alias="X-User-Id"),
    ] = None,
    x_organization_id: Annotated[
        uuid.UUID | None,
        Header(alias="X-Organization-Id"),
    ] = None,
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
) -> AuthenticatedContext:
    access_token = _bearer_token(authorization)

    if x_user_id is None or x_organization_id is None or access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated context headers",
        )

    return AuthenticatedContext(
        user_id=x_user_id,
        organization_id=x_organization_id,
        access_token=access_token,
    )


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token
