import json
import os
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

from modules import get_logger
from modules.agent_mod import MCPAgentModule

load_dotenv()
logger = get_logger(name="FastAPI", show_pid=False, show_time=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    logger.info("Starting MCP Hub server...")

    DATASTORE_DIR = Path(os.getenv("DATASTORE_DIR"))
    try:
        DATASTORE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Datastore directory ensured at {DATASTORE_DIR}")
    except PermissionError as e:
        logger.warning(f"Cannot create datastore directory: {e}")

    agent = MCPAgentModule()
    logger.info("Initializing AI agent...")
    await agent.init()
    logger.info("Agent ready!")
    yield
    logger.info("Shutting down MCP Hub server...")
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
        logger.info("Chat history deleted")
    if agent is not None:
        agent._clear_history()


app = FastAPI(title="MCP Hub API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"
HISTORY_FILE = Path(os.getenv("INTERNAL_DIR")) / "api_chat_history.json"
MAX_HISTORY = 30

agent: Optional[MCPAgentModule] = None


def _ensure_history_file() -> None:
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("[]")
    except PermissionError as e:
        logger.warning(f"Cannot create history file: {e}")


def _load_api_history() -> List[dict]:
    _ensure_history_file()
    try:
        data = HISTORY_FILE.read_text()
        if data.strip():
            return json.loads(data)
    except Exception:
        pass
    return []


def _save_api_history(history: List[dict]) -> None:
    _ensure_history_file()
    HISTORY_FILE.write_text(json.dumps(history[-MAX_HISTORY:], indent=2))


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    history: Optional[List[dict]] = None


class HistoryItem(BaseModel):
    question: str
    answer: str
    timestamp: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def home():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)


@app.get("/ping")
async def ping():
    return {
        "status": "ok",
        "message": "MCP Hub server is running",
        "agent_ready": agent is not None,
    }, 200


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response = await agent.invoke_agent(question=request.message)

        if hasattr(response, "content"):
            answer = response.content
        else:
            answer = str(response)

        _ensure_history_file()
        history = _load_api_history()
        history.append(
            {
                "question": request.message,
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
            }
        )
        _save_api_history(history)

        return ChatResponse(response=answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history():
    history = _load_api_history()
    return {"history": history}


@app.post("/api/clear")
async def clear_history():
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()

    if agent is not None:
        agent._clear_history()

    return {"status": "ok", "message": "History cleared"}


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "history_count": len(_load_api_history()),
    }


# if __name__ == "__main__":
#     uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
