from fastapi import FastAPI
from routers import auth, documents, application

app = FastAPI(title="Vendor Onboarding API", version="1.0.0")

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(application.router)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
