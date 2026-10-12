from fastapi import FastAPI

app = FastAPI(
    title="Document Search Service",
    description="API для полнотекстового поиска документов",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}