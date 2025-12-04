import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, UnstructuredEPubLoader
from loguru import logger

from llm_engineering.domain.documents import ArticleDocument

from .base import BaseCrawler


class DocumentCrawler(BaseCrawler):
    model = ArticleDocument

    def __init__(self) -> None:
        super().__init__()

    def extract(self, link: str, **kwargs) -> None:
        old_model = self.model.find(link=link)
        if old_model is not None:
            logger.info(f"Document already exists in the database: {link}")
            return

        logger.info(f"Starting extraction of document: {link}")

        file_path = Path(link)
        if not file_path.exists():
            logger.error(f"File not found: {link}")
            return

        file_extension = file_path.suffix.lower()

        if file_extension == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif file_extension == ".epub":
            loader = UnstructuredEPubLoader(str(file_path))
        else:
            logger.error(f"Unsupported file type: {file_extension}")
            return

        docs = loader.load()

        full_content = "\n\n".join([doc.page_content for doc in docs])

        title = file_path.stem
        metadata = docs[0].metadata if docs else {}

        content = {
            "Title": metadata.get("title", title),
            "Subtitle": metadata.get("subtitle"),
            "Content": full_content,
            "source": str(file_path),
        }

        platform = f"local_{file_extension[1:]}"

        user = kwargs["user"]
        instance = self.model(
            content=content,
            link=link,
            platform=platform,
            author_id=user.id,
            author_full_name=user.full_name,
        )
        instance.save()

        logger.info(f"Finished extracting document: {link}")
