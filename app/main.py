from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import get_base_prompt_repository, get_runtime_settings
from app.api.routes.prompts import router as prompts_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    try:
        if get_base_prompt_repository.cache_info().currsize:
            get_base_prompt_repository().close()
    except Exception:
        pass


app = FastAPI(title="Prompt Similarity Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_runtime_settings().frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(prompts_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
