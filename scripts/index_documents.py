import asyncio

from elasticsearch.helpers import async_bulk
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models import Document
from app.search import es_client, INDEX_NAME


async def index_documents():
    try:
        if not await es_client.indices.exists(index=INDEX_NAME):
            await es_client.indices.create(
                index=INDEX_NAME,
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

            print("Поисковый индекс создан!")

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document.id, Document.text)
            )
            documents = result.all()

        actions = [
            {
                "_index": INDEX_NAME,
                "_id": str(doc_id),
                "_source": {
                    "id": doc_id,
                    "text": text,
                },
            }
            for doc_id, text in documents
        ]

        if actions:
            success, _ = await async_bulk(
                es_client,
                actions,
                raise_on_error=True,
            )
        else:
            success = 0

        await es_client.indices.refresh(index=INDEX_NAME)

        print(f"Проиндексировано документов: {success}")

    finally:
        await es_client.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(index_documents())
