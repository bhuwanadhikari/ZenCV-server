from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import init_db
from routers.generation import router as generation_router
from routers.auth import router as auth_router
from routers.payment import router as payment_router
from services.config_service import config


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
app.include_router(payment_router)


# ===== Payment Web App =====
# Serve static files from app folder
app_folder = os.path.join(os.path.dirname(__file__), "app")
if os.path.exists(app_folder):
    app.mount("/payment", StaticFiles(directory=app_folder, html=True), name="payment")


@app.get("/")
async def root():
    """Redirect to payment page"""
    return FileResponse(os.path.join(app_folder, "index.html"))


@app.get("/api/config/stripe-key")
async def get_stripe_key():
    """Get Stripe public key for frontend"""
    return {
        "public_key": config.STRIPE_PUBLIC_KEY
    }
