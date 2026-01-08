def search_reports(keyword):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Perform the search with a projection and sort for the score
    results = collection.find(
        {"$text": {"$search": keyword}},
        {"score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]).limit(3)

    print(f"Top results for '{keyword}':")
    for doc in results:
        title = doc['report_metadata']['display_title']
        score = doc['score']
        print(f"- {title} (Relevance Score: {score:.2f})")

    client.close()

# Example:
# search_reports("agile scrum")