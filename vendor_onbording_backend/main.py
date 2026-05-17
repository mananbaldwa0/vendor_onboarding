import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, documents, application, admin

app = FastAPI(title="Vendor Onboarding API", version="1.0.0")

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(application.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
