import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langgraph.types import Command

from .agent.graph import build_graph, open_checkpointer

BASE_DIR = Path(__file__).resolve().parent

_executor = ThreadPoolExecutor(max_workers=4)
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AGENT_TIMEOUT_SECONDS", "300"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    with open_checkpointer() as checkpointer:
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


def _invoke_graph(graph, config, message=None, resume=None):
    if resume is not None:
        return graph.invoke(Command(resume=resume), config=config)
    return graph.invoke({"buyer_message": message, "thread_id": config["configurable"]["thread_id"]}, config=config)


@app.post("/api/agent")
def agent_turn(request: Request, body: dict):
    thread_id = body.get("thread_id", "").strip() if isinstance(body.get("thread_id"), str) else ""
    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required.")

    message = body.get("message")
    resume = body.get("resume")
    if not message and not resume:
        raise HTTPException(status_code=400, detail="Either 'message' or 'resume' is required.")

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}

    future = _executor.submit(_invoke_graph, graph, config, message=message, resume=resume)
    try:
        result = future.result(timeout=REQUEST_TIMEOUT_SECONDS)
    except FutureTimeoutError as err:
        raise HTTPException(status_code=504, detail="This is taking longer than expected — the agent may still be working.") from err
    except Exception as err:
        raise HTTPException(status_code=502, detail="The agent hit an error processing that request.") from err

    interrupts = result.get("__interrupt__")
    if interrupts:
        return {"status": "interrupted", "interrupt": interrupts[0].value}

    return {"status": "done", "summary": result.get("summary", "")}
