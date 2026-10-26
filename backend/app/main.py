from fastapi import FastAPI
from app.config import settings

app = FastAPI(
    title="Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
    description="Cloud VLM proposes robotic actions; an on-device local model and deterministic envelope hold hard veto authority over keep-out volumes and force limits; every veto is replayed in Nebius Serverless simulation as an auditable counterfactual.",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.environment}

@app.get("/v1/info")
def get_info():
    return {
        "project": "Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
        "track": "Physical AI",
        "models": {
            "ultra": settings.model_ultra,
            "super": settings.model_super,
            "nano": settings.model_nano
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
