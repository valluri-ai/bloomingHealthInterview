from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from app.data.sample_prompts import SAMPLE_PROMPTS
from app.repositories.prompt_repository import TenantAdminRepository
from app.repositories.tenant_scoped_prompt_repository import TenantScopedPromptRepository
from app.repositories.tenant_scoped_prompt_store import TenantScopedPromptStore
from app.services.prompt_ingestion_service import PromptIngestionService


TenantSeedType = Literal["empty", "sample", "benchmark_1k"]


class TenantService:
    def __init__(
        self,
        *,
        repo: TenantAdminRepository,
        prompt_store,
        benchmark_dataset_path: str,
    ) -> None:
        self.repo = repo
        self.prompt_store = prompt_store
        self.benchmark_dataset_path = Path(benchmark_dataset_path)

    def list_tenants(self):
        self.repo.ensure_schema()
        self._ensure_builtin_tenants()
        return [self._serialize_tenant(tenant) for tenant in self.repo.list_tenants()]

    def create_tenant(
        self,
        *,
        name: str,
        tenant_id: str | None = None,
        seed_type: TenantSeedType = "empty",
        is_builtin: bool = False,
    ):
        self.repo.ensure_schema()
        resolved_tenant_id = tenant_id or self._slugify(name)
        self.repo.create_tenant(
            tenant_id=resolved_tenant_id,
            name=name,
            is_builtin=is_builtin,
        )
        if seed_type != "empty" and self.repo.count_prompts_for_tenant(resolved_tenant_id) == 0:
            self._seed_tenant(resolved_tenant_id, seed_type)
        tenant = self.repo.get_tenant(resolved_tenant_id)
        if tenant is None:
            raise RuntimeError(f"Tenant {resolved_tenant_id} was not created")
        return self._serialize_tenant(tenant)

    def _ensure_builtin_tenants(self) -> None:
        builtins: list[tuple[str, str, TenantSeedType]] = [
            ("sample-prompts", "12 Prompt Sample", "sample"),
            ("benchmark-1k", "Benchmark 1K", "benchmark_1k"),
        ]
        for tenant_id, name, seed_type in builtins:
            tenant = self.repo.create_tenant(tenant_id=tenant_id, name=name, is_builtin=True)
            if tenant.prompt_count == 0:
                self._seed_tenant(tenant_id, seed_type)

    def _seed_tenant(self, tenant_id: str, seed_type: TenantSeedType) -> None:
        repo = TenantScopedPromptRepository(base_repo=self.repo, tenant_id=tenant_id)
        store = TenantScopedPromptStore(base_store=self.prompt_store, tenant_id=tenant_id)
        service = PromptIngestionService(repo=repo, prompt_store=store)
        service.ingest_prompts(self._load_seed_prompts(seed_type))

    def _load_seed_prompts(self, seed_type: TenantSeedType):
        if seed_type == "sample":
            return SAMPLE_PROMPTS
        if seed_type == "benchmark_1k":
            if not self.benchmark_dataset_path.exists():
                return []
            data = json.loads(self.benchmark_dataset_path.read_text())
            prompts = data.get("prompts", [])
            return [prompt if hasattr(prompt, "model_dump") else self._coerce_prompt(prompt) for prompt in prompts]
        return []

    def _coerce_prompt(self, payload: dict):
        from app.schemas.prompt import PromptInput

        return PromptInput(**payload)

    def _serialize_tenant(self, tenant):
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "prompt_count": tenant.prompt_count,
            "is_builtin": tenant.is_builtin,
            "created_at": None if tenant.created_at is None else str(tenant.created_at),
        }

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "tenant"
