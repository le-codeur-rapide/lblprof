# start_time = time.time()
import chromadb
import numpy as np
from chromadb.config import Settings

# 1. Set up ChromaDB in-memory client
client = chromadb.Client(Settings(anonymized_telemetry=False))

# 2. Create collection
collection = client.create_collection(name="demo_collection", get_or_create=True)

# 3. Add a few random vectors (dimension = 5)
np.random.seed(42)
n_vectors = 5
dim = 5

for i in range(n_vectors):
    vector = np.random.rand(dim).tolist()
    collection.add(
        ids=[f"vec_{i}"],
        embeddings=[vector],
        metadatas=[{"index": i}],
        documents=[f"Random vector #{i}"],
    )


# 4. Create a random query vector
query_vector = np.random.rand(dim).tolist()

# 5. Perform similarity search
results = collection.query(
    query_embeddings=[query_vector],
    n_results=3,
    include=["embeddings", "metadatas", "documents"],
)

# print(f"Time taken: {time.time() - start_time} seconds")
