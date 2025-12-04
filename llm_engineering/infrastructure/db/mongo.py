from loguru import logger
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from llm_engineering.settings import settings
from llm_engineering.domain.exceptions import ImproperlyConfigured


class LazyMongoConnection:
    """Lazily initializes a MongoClient on first use to avoid import-time failures."""

    _client: MongoClient | None = None

    def _ensure_client(self) -> MongoClient:
        if self._client is not None:
            return self._client
        try:
            # Set short timeouts so we fail fast with a clear error message
            self._client = MongoClient(
                settings.DATABASE_HOST,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
            )
            # Proactively check connectivity to provide actionable feedback early
            self._client.admin.command("ping")
            logger.info(f"Connection to MongoDB with URI successful: {settings.DATABASE_HOST}")
            return self._client
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            message = (
                "Couldn't connect to MongoDB at "
                f"{settings.DATABASE_HOST}. Make sure MongoDB is running. "
                "If you're running locally, start it with 'docker-compose up -d' "
                "or point DATABASE_HOST to a reachable instance via your .env or ZenML secret."
            )
            logger.error(message)
            raise ImproperlyConfigured(message) from e

    def get_database(self, name: str):
        client = self._ensure_client()
        return client.get_database(name)


# Public module-level handle used throughout the codebase
connection = LazyMongoConnection()
