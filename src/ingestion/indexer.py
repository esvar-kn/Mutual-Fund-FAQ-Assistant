import chromadb
from sentence_transformers import SentenceTransformer

class BGEEmbeddingFunction:
    """Custom embedding function for ChromaDB utilizing BGE model."""
    def __init__(self, model_name):
        print(f"Initializing SentenceTransformer with model: {model_name}")
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

class DocumentIndexer:
    """Handles connection to ChromaDB, collection management, and vector indexing."""
    @staticmethod
    def index_chunks(chunks, metadatas, ids, db_path, collection_name, model_name, embeddings=None):
        """
        Connects to ChromaDB, deletes existing collection if present, creates a new one,
        and adds the chunks along with their metadatas and ids.
        """
        print(f"-> Indexer connecting to ChromaDB at: {db_path}")
        chroma_client = chromadb.PersistentClient(path=str(db_path))
        
        # Clear collection if exists to avoid stale indexes
        try:
            chroma_client.delete_collection(name=collection_name)
            print(f"-> Cleared existing ChromaDB collection: {collection_name}")
        except Exception:
            pass
            
        # Clean up orphaned UUID segment directories on disk to prevent accumulation
        import re
        import shutil
        from pathlib import Path
        db_path_obj = Path(db_path)
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        if db_path_obj.exists():
            for entry in db_path_obj.iterdir():
                if entry.is_dir() and uuid_pattern.match(entry.name):
                    try:
                        shutil.rmtree(entry)
                        print(f"-> Deleted orphaned index directory: {entry.name}")
                    except Exception as e:
                        print(f"-> Failed to delete orphaned directory {entry.name}: {e}")

        bge_embedding = BGEEmbeddingFunction(model_name)
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=bge_embedding
        )
        
        # Write to vector database
        print("-> Writing vector chunks to database...")
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print("-> Vector indexing completed successfully!")
