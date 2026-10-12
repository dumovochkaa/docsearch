from datetime import datetime, timedelta
from importlib import import_module
from uuid import uuid4

import pytest
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, DATABASE_URL
from app.main import app
from app.models import Document
from app.search import ELASTICSEARCH_URL


@pytest.mark.asyncio
async def test_search_and_delete_integration(monkeypatch):
    main = import_module("app.main")

    test_url = DATABASE_URL.set(database="document_search_test")

    test_engine = create_async_engine(test_url)
    test_session = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )

    test_index = f"documents_test_{uuid4().hex}"
    test_es = AsyncElasticsearch(ELASTICSEARCH_URL)

    created_ids = []

    try:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await test_es.indices.create(
            index=test_index,
            mappings={
                "properties": {
                    "id": {"type": "integer"},
                    "text": {
                        "type": "text",
                        "analyzer": "russian",
                    },
                }
            },
        )

        monkeypatch.setattr(main, "AsyncSessionLocal", test_session)
        monkeypatch.setattr(main, "es_client", test_es)
        monkeypatch.setattr(main, "INDEX_NAME", test_index)

        async with test_session() as session:
            documents = [
                Document(
                    rubrics=["test"],
                    text=f"Проверка поиска документа номер {i}",
                    created_date=(
                        datetime(2024, 1, 1) + timedelta(days=i)
                    ),
                )
                for i in range(25)
            ]

            session.add_all(documents)
            await session.flush()

            created_ids = [doc.id for doc in documents]
            await session.commit()

        actions = [
            {
                "_index": test_index,
                "_id": str(doc.id),
                "_source": {
                    "id": doc.id,
                    "text": doc.text,
                },
            }
            for doc in documents
        ]

        await async_bulk(test_es, actions)
        await test_es.indices.refresh(index=test_index)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            response = await client.get(
                "/search",
                params={"q": "проверка"},
            )

            assert response.status_code == 200

            results = response.json()

            assert len(results) == 20

            expected_ids = list(reversed(created_ids[-20:]))

            assert [doc["id"] for doc in results] == expected_ids

            assert set(results[0]) == {
                "id",
                "rubrics",
                "text",
                "created_date",
            }

            document_id = created_ids[-1]

            response = await client.delete(
                f"/documents/{document_id}"
            )

            assert response.status_code == 204

            async with test_session() as session:
                deleted_document = await session.get(
                    Document,
                    document_id,
                )

            assert deleted_document is None

            exists = await test_es.exists(
                index=test_index,
                id=str(document_id),
            )

            assert not exists

            response = await client.delete(
                f"/documents/{document_id}"
            )

            assert response.status_code == 404

    finally:
        try:
            await test_es.indices.delete(
                index=test_index,
                ignore_unavailable=True,
            )
        finally:
            try:
                if created_ids:
                    async with test_session() as session:
                        await session.execute(
                            delete(Document).where(
                                Document.id.in_(created_ids)
                            )
                        )
                        await session.commit()
            finally:
                await test_es.close()
                await test_engine.dispose()
