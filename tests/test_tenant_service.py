from __future__ import annotations

from app.domain.models import TenantRecord
from app.services.tenant_service import TenantService


class StubTenantRepo:
    def ensure_schema(self) -> None:
        return None

    def list_tenants(self) -> list[TenantRecord]:
        return [
            TenantRecord(
                tenant_id="sample-prompts",
                name="Sample Prompts",
                prompt_count=12,
                is_builtin=True,
                created_at=1775699233100,  # type: ignore[arg-type]
            )
        ]

    def get_tenant(self, tenant_id: str) -> TenantRecord | None:
        return TenantRecord(tenant_id=tenant_id, name=tenant_id, prompt_count=12, is_builtin=True, created_at=None)

    def create_tenant(self, *, tenant_id: str, name: str, is_builtin: bool = False) -> TenantRecord:
        return TenantRecord(
            tenant_id=tenant_id,
            name=name,
            prompt_count=12 if is_builtin else 0,
            is_builtin=is_builtin,
            created_at=None,
        )

    def count_prompts_for_tenant(self, tenant_id: str) -> int:
        return 12


def test_list_tenants_serializes_created_at_as_string() -> None:
    service = TenantService(
        repo=StubTenantRepo(),
        prompt_store=object(),
        benchmark_dataset_path="tmp/does-not-matter.json",
    )

    tenants = service.list_tenants()

    assert tenants == [
        {
            "tenant_id": "sample-prompts",
            "name": "Sample Prompts",
            "prompt_count": 12,
            "is_builtin": True,
            "created_at": "1775699233100",
        }
    ]
