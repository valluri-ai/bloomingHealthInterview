from app.api import dependencies
from app.core.config import get_settings
from app.repositories.filesystem_prompt_store import FilesystemPromptStore


def test_get_base_prompt_store_defaults_to_local_filesystem_when_s3_bucket_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("PROMPT_S3_BUCKET", raising=False)
    monkeypatch.setenv("PROMPT_STORE_ROOT", str(tmp_path))

    dependencies.get_base_prompt_store.cache_clear()
    get_settings.cache_clear()

    store = dependencies.get_base_prompt_store()

    assert isinstance(store, FilesystemPromptStore)
    assert store.root == tmp_path

    dependencies.get_base_prompt_store.cache_clear()
    get_settings.cache_clear()
