import chromadb
from sentence_transformers import SentenceTransformer

from src.config import (
    DB_DIR,
    EMBEDDING_MODEL_NAME,
    CHROMA_COLLECTION_NAME
)

class BGEEmbeddingFunction:
    """Custom embedding function for ChromaDB utilizing BGE model."""
    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input):
        embeddings = self.model.encode(input, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, input):
        return self.__call__(input)

    def embed_documents(self, input):
        return self.__call__(input)

    def name(self):
        return "BGEEmbeddingFunction"

class MutualFundRetriever:
    """Handles ChromaDB connection, query embedding, and semantic similarity search."""
    def __init__(self, db_path=DB_DIR):
        print(f"Connecting to ChromaDB at: {db_path}")
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.embedding_fn = BGEEmbeddingFunction()
        self.collection = self.client.get_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

    def retrieve_context(self, query, scheme_filter=None, amc_filter=None, top_k=4):
        """
        Embeds query and queries ChromaDB.
        Applies metadata filters for scheme_name or amc_name if specified.
        """
        # Prepare filters
        where_filter = None
        filters = []
        if scheme_filter:
            filters.append({"scheme_name": scheme_filter})
        if amc_filter:
            filters.append({"amc_name": amc_filter})

        if len(filters) == 1:
            where_filter = filters[0]
        elif len(filters) > 1:
            where_filter = {"$and": filters}

        # Query database
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter
        )

        # Re-format output records
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        formatted_chunks = []
        for i in range(len(documents)):
            formatted_chunks.append({
                "text": documents[i],
                "source_url": metadatas[i].get("source_url"),
                "scheme_name": metadatas[i].get("scheme_name"),
                "amc_name": metadatas[i].get("amc_name"),
                "doc_type": metadatas[i].get("doc_type"),
                "last_updated_date": metadatas[i].get("last_updated_date"),
                "distance": distances[i]
            })
        return formatted_chunks
