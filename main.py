from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.generation import router as generation_router


app = FastAPI(
    title="IntelliCV Server",
    version="0.1.0",
    description="Backend for browser-extension powered CV and cover letter generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generation_router)
