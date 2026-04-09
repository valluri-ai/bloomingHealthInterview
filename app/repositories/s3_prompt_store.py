from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.domain.models import StoredPromptVersion
from app.repositories.prompt_repository import PromptTemplateStore
from app.schemas.prompt import PromptInput


class S3PromptStore(PromptTemplateStore):
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "prompts",
        client: Any | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client or boto3.client("s3")

    def store_prompt(self, prompt: PromptInput) -> StoredPromptVersion:
        key = f"{self.prefix}/{prompt.prompt_id}.json"
        return self._store_prompt_at_key(prompt=prompt, key=key)

    def store_prompt_for_tenant(self, tenant_id: str, prompt: PromptInput) -> StoredPromptVersion:
        key = f"{self.prefix}/tenants/{tenant_id}/{prompt.prompt_id}.json"
        return self._store_prompt_at_key(prompt=prompt, key=key)

    def _store_prompt_at_key(self, *, prompt: PromptInput, key: str) -> StoredPromptVersion:
        body = json.dumps(prompt.model_dump(mode="json"), indent=2).encode("utf-8")
        response = self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        return StoredPromptVersion(
            bucket=self.bucket,
            key=key,
            version_id=response.get("VersionId"),
            etag=response.get("ETag"),
            s3_uri=f"s3://{self.bucket}/{key}",
        )

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        key = f"{self.prefix}/{prompt_id}.json"
        return self.get_prompt_by_storage(key=key, bucket=self.bucket)

    def get_prompt_for_tenant(self, tenant_id: str, prompt_id: str) -> dict[str, Any] | None:
        key = f"{self.prefix}/tenants/{tenant_id}/{prompt_id}.json"
        return self.get_prompt_by_storage(key=key, bucket=self.bucket)

    def get_prompt_by_storage(
        self,
        *,
        key: str,
        bucket: str | None = None,
        version_id: str | None = None,
    ) -> dict[str, Any] | None:
        no_such_key_error = getattr(getattr(self.client, "exceptions", None), "NoSuchKey", None)
        try:
            request: dict[str, Any] = {"Bucket": bucket or self.bucket, "Key": key}
            if version_id:
                request["VersionId"] = version_id
            response = self.client.get_object(**request)
        except Exception as exc:
            if no_such_key_error and isinstance(exc, no_such_key_error):
                return None
            if isinstance(exc, ClientError):
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NoSuchVersion"}:
                    return None
                raise
            if isinstance(exc, KeyError):
                return None
            raise
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
