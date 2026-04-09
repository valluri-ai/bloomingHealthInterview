from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.models import StoredPromptVersion
from app.repositories.prompt_repository import PromptTemplateStore
from app.schemas.prompt import PromptInput


class FilesystemPromptStore(PromptTemplateStore):
    def __init__(self, *, root: str = "tmp/prompt_store") -> None:
        self.root = Path(root)

    def store_prompt(self, prompt: PromptInput) -> StoredPromptVersion:
        key = f"prompts/{prompt.prompt_id}.json"
        return self._store_prompt_at_key(prompt=prompt, key=key)

    def store_prompt_for_tenant(self, tenant_id: str, prompt: PromptInput) -> StoredPromptVersion:
        key = f"prompts/tenants/{tenant_id}/{prompt.prompt_id}.json"
        return self._store_prompt_at_key(prompt=prompt, key=key)

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        return self.get_prompt_by_storage(key=f"prompts/{prompt_id}.json", bucket="local")

    def get_prompt_for_tenant(self, tenant_id: str, prompt_id: str) -> dict[str, Any] | None:
        return self.get_prompt_by_storage(key=f"prompts/tenants/{tenant_id}/{prompt_id}.json", bucket="local")

    def get_prompt_by_storage(
        self,
        *,
        key: str,
        bucket: str | None = None,
        version_id: str | None = None,
    ) -> dict[str, Any] | None:
        del version_id
        if bucket not in {None, "local"}:
            return None
        path = self.root / key
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _store_prompt_at_key(self, *, prompt: PromptInput, key: str) -> StoredPromptVersion:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(prompt.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return StoredPromptVersion(
            bucket="local",
            key=key,
            version_id=None,
            etag=None,
            s3_uri=path.resolve().as_uri(),
        )
