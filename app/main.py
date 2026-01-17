from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.worker import start_worker
from app.config.env_config import env
from app.routes.chat_route import router
import threading

# Only define and use lifespan handler in development
if env.ENVIRONMENT != "production":
    # Lifespan event handler for development (replaces deprecated on_event)
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        thread = threading.Thread(target=start_worker, daemon=True)
        thread.start()
        print("✅ Pub/Sub worker started in background (development mode)")

        yield  # App is running

        # Shutdown (if needed)
        print("👋 Shutting down worker...")

    app = FastAPI(title="Chat bot Worker", lifespan=lifespan)
else:
    app = FastAPI(title="Chat bot Worker")

@app.get("/")
async def root():
    return {"status": "ok"}

app.include_router(router)

