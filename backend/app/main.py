from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import clinical, meta, pubmed

settings = get_settings()

app = FastAPI(
    title="Medical AI Training Hub",
    description="Multi-agent medical training app: CST clinical stations, PubMed matching, literature chat.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(clinical.router)
app.include_router(pubmed.router)


@app.get("/")
def root():
    return {
        "name": "Medical AI Training Hub",
        "docs": "/docs",
        "agents": "/api/agents",
    }
