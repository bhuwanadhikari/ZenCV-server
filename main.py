from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers.generation import router as generation_router
from routers.auth import router as auth_router


app = FastAPI(
    title="ZenCV Server",
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

# Initialize database
init_db()

app.include_router(generation_router)
app.include_router(auth_router)
