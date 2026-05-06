from fastapi import FastAPI
from api.routes.jobs import router as jobs_router

app = FastAPI()
app.include_router(jobs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
