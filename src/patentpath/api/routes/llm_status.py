"""GET /v1/llm/status: provider and circuit-breaker health."""

from fastapi import APIRouter

from patentpath.api.deps import GatewayDependency

router = APIRouter(prefix="/v1/llm", tags=["LLM"])


@router.get("/status")
async def llm_status(gateway: GatewayDependency):
    """Return each configured provider and its circuit-breaker state."""
    return {
        "providers": [
            {
                "name": provider.name,
                "model": provider.model,
                "breaker_state": gateway.breakers[provider.name].state,
            }
            for provider in gateway.providers
        ]
    }
