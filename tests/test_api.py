import pytest

from httpx import ASGITransport, AsyncClient

from app.main import app

from unittest.mock import AsyncMock
from importlib import import_module

from datetime import datetime
from unittest.mock import MagicMock

from app.models import Document

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_search_without_query():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/search")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_with_invalid_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete("/documents/abc")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_document(monkeypatch):
    main = import_module("app.main")

    session = AsyncMock()
    session.get.return_value = None

    session_context = AsyncMock()
    session_context.__aenter__.return_value = session

    monkeypatch.setattr(
        main,
        "AsyncSessionLocal",
        lambda: session_context,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete("/documents/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found"
    }


@pytest.mark.asyncio
async def test_delete_existing_document(monkeypatch):
    main = import_module("app.main")

    document = object()

    session = AsyncMock()
    session.get.return_value = document

    session_context = AsyncMock()
    session_context.__aenter__.return_value = session

    fake_elasticsearch = AsyncMock()

    monkeypatch.setattr(
        main,
        "AsyncSessionLocal",
        lambda: session_context,
    )
    monkeypatch.setattr(main, "es_client", fake_elasticsearch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete("/documents/999")

    assert response.status_code == 204
    assert response.content == b""

    fake_elasticsearch.delete.assert_awaited_once_with(
        index="documents",
        id="999",
        refresh="wait_for",
    )

    session.delete.assert_awaited_once_with(document)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_no_results(monkeypatch):
    main = import_module("app.main")

    async def fake_scan(*args, **kwargs):
        if False:
            yield None

    monkeypatch.setattr(main, "async_scan", fake_scan)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/search",
            params={"q": "несуществующее слово"},
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_query_order_and_limit(monkeypatch):
    main = import_module("app.main")

    async def fake_scan(*args, **kwargs):
        yield {"_source": {"id": 8}}
        yield {"_source": {"id": 3}}

    monkeypatch.setattr(main, "async_scan", fake_scan)

    documents = [
        Document(
            id=8,
            rubrics=["Новости"],
            text="Новый конкурс",
            created_date=datetime(2024, 5, 20),
        ),
        Document(
            id=3,
            rubrics=["События"],
            text="Старый конкурс",
            created_date=datetime(2023, 3, 10),
        ),
    ]

    result = MagicMock()
    result.scalars.return_value.all.return_value = documents

    session = AsyncMock()
    session.execute.return_value = result

    session_context = AsyncMock()
    session_context.__aenter__.return_value = session

    monkeypatch.setattr(
        main,
        "AsyncSessionLocal",
        lambda: session_context,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/search",
            params={"q": "конкурс"},
        )

    assert response.status_code == 200
    assert [doc["id"] for doc in response.json()] == [8, 3]

    statement = session.execute.await_args.args[0]

    sql = str(
        statement.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert "ORDER BY documents.created_date DESC, documents.id DESC" in sql
    assert "LIMIT 20" in sql
