"""HTTP surface of the laboratory mode (mounted only when ``LAB_MODE`` is on)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ai_core.api.deps import Authenticated, ContainerDep
from ai_core.errors import NotFound


class SwitchIn(BaseModel):
    down: bool


def build_lab_router() -> APIRouter:
    router = APIRouter(prefix="/v1/lab", tags=["lab"])

    @router.get("/config")
    async def config(c: ContainerDep) -> dict[str, object]:
        """Open on purpose: lets the sign-in page say whether the well-known development key is in use."""
        return {"lab": True, "default_key_in_use": c.settings.api_key.get_secret_value() == "change-me"}

    @router.get("/state", dependencies=[Authenticated])
    async def state(c: ContainerDep) -> dict[str, object]:
        assert c.lab is not None
        breakers = c.router.breaker_states()
        secrets = c.settings.webhook_secret_list
        return {
            "providers": [
                {"name": p.name, "locality": p.locality.value, "down": p.down, "breaker": breakers[p.name].value}
                for p in c.lab.switches.values()
            ],
            "webhook_secret": secrets[0] if secrets else None,
            "webhook_tolerance_seconds": c.settings.webhook_tolerance_seconds,
            "allowed_sources": c.settings.allowed_source_patterns,
        }

    @router.post("/providers/{name}", dependencies=[Authenticated])
    async def switch(name: str, body: SwitchIn, c: ContainerDep) -> dict[str, object]:
        assert c.lab is not None
        provider = c.lab.switches.get(name)
        if provider is None:
            raise NotFound(f"no provider named {name!r}")
        provider.down = body.down
        return {"name": name, "down": provider.down}

    @router.post("/breakers/reset", dependencies=[Authenticated])
    async def reset_breakers(c: ContainerDep) -> dict[str, str]:
        c.router.reset_breakers()
        return {name: state.value for name, state in c.router.breaker_states().items()}

    @router.post("/reset", dependencies=[Authenticated])
    async def reset(c: ContainerDep) -> dict[str, bool]:
        """Start over: providers up, breakers closed, inbox empty, knowledge base empty.

        Webhook event ids are deliberately left alone: they expire by TTL, and forgetting them would let an old
        capture replay (the lab generates fresh ids, so it never notices).
        """
        assert c.lab is not None
        c.lab.reset()
        c.router.reset_breakers()
        await c.store.clear()
        return {"reset": True}

    @router.get("/cloud-inbox", dependencies=[Authenticated])
    async def cloud_inbox(c: ContainerDep) -> dict[str, object]:
        """Everything the simulated third-party API has received, newest last."""
        assert c.lab is not None
        return {"received": list(c.lab.cloud.received) if c.lab.cloud else []}

    return router
