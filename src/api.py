import asyncio
import time
from pathlib import Path

import setproctitle
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from .executor import execute_node

app = FastAPI(title="dazflow2")

SERVER_START_TIME = time.time()
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files for nodes directory (must be before routes)
app.mount("/nodes", StaticFiles(directory=STATIC_DIR / "nodes"), name="nodes")


# ##################################################################
# heartbeat generator
# yields server-sent events with the server start time so clients
# can detect when the server has restarted and reload the page
async def heartbeat_generator():
    while True:
        yield f"data: {SERVER_START_TIME}\n\n"
        await asyncio.sleep(2)


# ##################################################################
# health check
# simple endpoint to verify the server is running
@app.get("/health")
async def health():
    return {"status": "ok", "start_time": SERVER_START_TIME}


# ##################################################################
# heartbeat stream
# server-sent events endpoint that clients use to detect server restarts
@app.get("/heartbeat")
async def heartbeat():
    return StreamingResponse(
        heartbeat_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ##################################################################
# serve index
# serves the main frontend shell html page
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path, media_type="text/html")


# ##################################################################
# execute node endpoint
# executes a node (and its upstream dependencies if needed)
class ExecuteRequest(BaseModel):
    node_id: str
    workflow: dict
    execution: dict


class ExecuteResponse(BaseModel):
    execution: dict


@app.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute a node and return updated execution state."""
    updated_execution = execute_node(
        node_id=request.node_id,
        workflow=request.workflow,
        execution=request.execution,
    )
    return ExecuteResponse(execution=updated_execution)


# ##################################################################
# main entry
# starts the uvicorn server with the configured number of workers
def main():
    import uvicorn

    setproctitle.setproctitle("dazflow2-api")
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=31415,
        workers=10,
        reload=False,
    )


# ##################################################################
# standard dispatch
if __name__ == "__main__":
    main()
