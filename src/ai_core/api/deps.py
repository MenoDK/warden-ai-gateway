from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from ai_core.container import Container
from ai_core.errors import Unauthorized


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_api_key(
    container: ContainerDep,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = container.settings.api_key.get_secret_value().encode()
    # compare_digest on equal-type bytes: constant time, no early exit on the first byte.
    if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), expected):
        raise Unauthorized("missing or invalid API key")


Authenticated = Depends(require_api_key)
