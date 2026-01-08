import os
from datetime import datetime
from pymongo import MongoClient
from pypdf import PdfReader

# --- Configuration ---
MONGO_URI = "mongodb://llm_engineering:llm_engineering@localhost:27017"
DB_NAME = "reports"
COLLECTION_NAME = "quarterly_reports"
SOURCE_FOLDER = "/Volumes/MacMiniX/P_Drive_Ext/PDF/IT MANAGEMENT BY TAYLOR & FRANCIS/"


def get_pdf_info(filepath):
    """Extracts text, page count, and metadata title from a PDF."""
    reader = PdfReader(filepath)

    # 1. Extract Text
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"

    # 2. Try to get a better title from PDF metadata
    meta = reader.metadata
    filename = os.path.basename(filepath)
    # Use metadata title if it exists and isn't just whitespace
    clean_title = meta.title if meta and meta.title and meta.title.strip() else filename

    return text, len(reader.pages), clean_title


def batch_upload():
    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Ensure the folder exists
    if not os.path.exists(SOURCE_FOLDER):
        print(f"Error: Folder not found at {SOURCE_FOLDER}")
        return

    files = [f for f in os.listdir(SOURCE_FOLDER) if f.lower().endswith('.pdf')]
    print(f"Found {len(files)} PDFs. Starting upload...")

    for filename in files:
        file_path = os.path.join(SOURCE_FOLDER, filename)

        try:
            raw_text, pages, display_title = get_pdf_info(file_path)

            report_doc = {
                "report_metadata": {
                    "display_title": display_title,
                    "original_filename": filename,
                    "pages": pages,
                    "processed_at": datetime.utcnow(),
                    "source_path": file_path
                },
                "content": {
                    "raw_text": raw_text,
                    "char_count": len(raw_text)
                }
            }

            collection.insert_one(report_doc)
            print(f"Uploaded: {display_title} ({pages} pages)")

        except Exception as e:
            print(f"Failed to process {filename}: {e}")

    client.close()
    print("Batch upload complete.")


if __name__ == "__main__":
    batch_upload()