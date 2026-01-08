import os
from datetime import datetime
from pymongo import MongoClient
from pypdf import PdfReader
from ebooklib import epub
from bs4 import BeautifulSoup

# --- Configuration ---
MONGO_URI = "mongodb://llm_engineering:llm_engineering@localhost:27017"
DB_NAME = "reports"
COLLECTION_NAME = "quarterly_reports"


def extract_pdf_text(filepath):
    """Extracts text from each page of a PDF."""
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text, len(reader.pages)


def extract_epub_text(filepath):
    """Extracts and cleans text from an EPUB file."""
    book = epub.read_epub(filepath)
    text_parts = []
    # EPUBs store text in 'documents' (usually HTML)
    for item in book.get_items_of_type(1):  # 1 is ebooklib.ITEM_DOCUMENT
        soup = BeautifulSoup(item.get_body_content(), 'html.parser')
        text_parts.append(soup.get_text())

    full_text = "\n".join(text_parts)
    return full_text, "N/A (EPUB)"


def upload_report(file_path):
    # 1. Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # 2. Extract content based on file type
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    print(f"Processing {filename}...")

    if ext == ".pdf":
        raw_text, pages = extract_pdf_text(file_path)
    elif ext == ".epub":
        raw_text, pages = extract_epub_text(file_path)
    else:
        print(f"Unsupported format: {ext}")
        return

    # 3. Prepare the document
    report_doc = {
        "report_metadata": {
            "title": filename,
            "file_extension": ext,
            "pages": pages,
            "processed_at": datetime.utcnow(),
            "version": 1
        },
        "content": {
            "raw_text": raw_text,
            "char_count": len(raw_text)
        }
    }

    # 4. Insert into MongoDB
    result = collection.insert_one(report_doc)
    print(f"Successfully uploaded! ID: {result.inserted_id}")
    client.close()


if __name__ == "__main__":
    # Example usage:
    # replace with the actual path to your report
    target_file = "/Users/scottc/Documents/sample_report.pdf"
    if os.path.exists(target_file):
        upload_report(target_file)
    else:
        print("File not found. Please check the path.")