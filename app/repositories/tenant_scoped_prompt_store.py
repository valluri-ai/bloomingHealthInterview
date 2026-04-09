from __future__ import annotations

from typing import Any

from app.repositories.prompt_repository import PromptTemplateStore
from app.schemas.prompt import PromptInput


class TenantScopedPromptStore(PromptTemplateStore):
    def __init__(self, *, base_store: Any, tenant_id: str) -> None:
        self.base_store = base_store
        self.tenant_id = tenant_id

    def store_prompt(self, prompt: PromptInput):
        return self.base_store.store_prompt_for_tenant(self.tenant_id, prompt)

    def get_prompt(self, prompt_id: str):
        return self.base_store.get_prompt_for_tenant(self.tenant_id, prompt_id)

    def get_prompt_by_storage(
        self,
        *,
        key: str,
        bucket: str | None = None,
        version_id: str | None = None,
    ) -> dict[str, Any] | None:
        request: dict[str, Any] = {"key": key}
        if bucket is not None:
            request["bucket"] = bucket
        if version_id is not None:
            request["version_id"] = version_id
        return self.base_store.get_prompt_by_storage(**request)
