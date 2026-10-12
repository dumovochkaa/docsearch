import asyncio
import ast
import csv

from datetime import datetime
from pathlib import Path

from sqlalchemy import select, func

from app.database import AsyncSessionLocal, engine
from app.models import Document


CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "posts.csv"


def read_documents() -> list[Document]:
    documents = []

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rubrics = ast.literal_eval(row["rubrics"])

            document = Document(
                text=row["text"],
                rubrics=rubrics,
                created_date=datetime.fromisoformat(row["created_date"]),
            )

            documents.append(document)

    return documents


async def import_documents():
    try:
        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count()).select_from(Document)
            )

            if count > 0:
                print(f"В базе уже есть {count} документов. Импорт пропущен.")
                return

            documents = read_documents()

            session.add_all(documents)
            await session.commit()

            print(f"Успешно загружено {len(documents)} документов!")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_documents())
