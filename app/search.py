import os

from elasticsearch import AsyncElasticsearch

INDEX_NAME = "documents"

ELASTICSEARCH_URL = os.getenv(
    "ELASTICSEARCH_URL",
    "http://127.0.0.1:9200",
)

es_client = AsyncElasticsearch(ELASTICSEARCH_URL)
