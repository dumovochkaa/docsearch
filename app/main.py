from contextlib import asynccontextmanager

from elasticsearch.helpers import async_scan
from fastapi import FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models import Document
from app.schemas import DocumentResponse
from app.search import es_client, INDEX_NAME
from elasticsearch import NotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await es_client.close()
    await engine.dispose()


app = FastAPI(
    title="DocSearch",
    description="Асинхронный REST API для полнотекстового поиска и удаления документов",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/search", response_model=list[DocumentResponse])
async def search_documents(
    q: str = Query(min_length=1, description="Текст поискового запроса"),
):
    search_text = q.strip()

    if not search_text:
        raise HTTPException(
            status_code=422,
            detail="Поисковый запрос не может быть пустым",
        )

    document_ids = []

    async for hit in async_scan(
        es_client,
        index=INDEX_NAME,
        query={
            "_source": ["id"],
            "query": {
                "match": {
                    "text": search_text
                }
            },
        },
    ):
        document_ids.append(hit["_source"]["id"])

    if not document_ids:
        return []

    async with AsyncSessionLocal() as session:
        statement = (
            select(Document)
            .where(Document.id.in_(document_ids))
            .order_by(
                Document.created_date.desc(),
                Document.id.desc(),
            )
            .limit(20)
        )

        result = await session.execute(statement)
        documents = result.scalars().all()

        return documents


@app.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(document_id: int):
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        try:
            await es_client.delete(
                index=INDEX_NAME,
                id=str(document_id),
                refresh="wait_for",
            )
        except NotFoundError:
            pass

        await session.delete(document)
        await session.commit()

    return Response(status_code=204)
