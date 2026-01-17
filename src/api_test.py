from fastapi.testclient import TestClient

from src.api import app


# ##################################################################
# test health endpoint
# verifies the health endpoint returns expected structure
def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "start_time" in data
    assert isinstance(data["start_time"], float)


# ##################################################################
# test index page
# verifies the root endpoint serves html
def test_index_serves_html():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "dazflow2" in response.text


# ##################################################################
# test heartbeat generator
# verifies the heartbeat generator produces correct sse format
def test_heartbeat_generator():
    import asyncio
    from src.api import heartbeat_generator, SERVER_START_TIME

    async def get_first_heartbeat():
        gen = heartbeat_generator()
        return await gen.__anext__()

    result = asyncio.run(get_first_heartbeat())
    assert result.startswith("data:")
    assert result.endswith("\n\n")
    # verify the data contains the server start time
    timestamp = float(result.replace("data:", "").strip())
    assert timestamp == SERVER_START_TIME
