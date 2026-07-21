import os
import re

from src.config import (
    RAW_DIR,
    PROCESSED_DIR,
    DB_DIR,
    HEADERS,
    EMBEDDING_MODEL_NAME,
    CHROMA_COLLECTION_NAME,
    SCHEMES_LIST
)
from src.ingestion.fetcher import DocumentFetcher
from src.ingestion.parser import DocumentParser
from src.ingestion.chunker import DocumentChunker
from src.ingestion.indexer import DocumentIndexer, BGEEmbeddingFunction

def slugify(text):
    """Helper to convert string into safe folder/file names."""
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')

def cleanup_legacy_outputs(data_parent):
    """Deletes any legacy global raw, processed, runs, and Corpus folders under data/ to prevent stale records."""
    import shutil
    legacy_raw = data_parent / "raw"
    legacy_processed = data_parent / "processed"
    legacy_runs = data_parent / "runs"
    corpus_dir = data_parent / "Corpus"
    
    for folder in [legacy_raw, legacy_processed, legacy_runs, corpus_dir]:
        if folder.exists():
            try:
                shutil.rmtree(folder)
                print(f"Deleted legacy global folder: {folder}")
            except Exception as e:
                print(f"Error deleting legacy global folder {folder}: {e}")

def run_ingestion():
    import datetime
    import json
    import shutil
    
    data_parent = DB_DIR.parent
    
    # 1. Clean up legacy global outputs
    cleanup_legacy_outputs(data_parent)
    
    # Create Corpus folder
    run_dir = data_parent / "Corpus"
    raw_dir = run_dir / "raw"
    processed_dir = run_dir / "processed"
    
    print("==================================================")
    print("Starting Ingestion Pipeline for Run: Corpus...")
    print("==================================================")
    
    # Ensure nested subdirectories are initialized
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Fetch, Parse, and Save Raw HTML & Processed JSON
    for scheme in SCHEMES_LIST:
        scheme_name = scheme.get("name", "Unknown Scheme")
        amc_name = scheme.get("amc_name", "Unknown AMC")
        url = scheme.get("url")
        category = scheme.get("category", "N/A")
        
        amc_slug = slugify(amc_name)
        scheme_slug = slugify(scheme_name)
        
        # Paths
        raw_amc_dir = raw_dir / amc_slug
        processed_amc_dir = processed_dir / amc_slug
        
        raw_amc_dir.mkdir(parents=True, exist_ok=True)
        processed_amc_dir.mkdir(parents=True, exist_ok=True)
        
        raw_html_path = raw_amc_dir / f"{scheme_slug}.html"
        processed_json_path = processed_amc_dir / f"{scheme_slug}.json"
        
        print(f"\nProcessing: {scheme_name} (AMC: {amc_name})")
        
        # Crawl raw HTML
        success, html_content = DocumentFetcher.fetch_and_save_html(
            url=url,
            raw_html_path=raw_html_path,
            headers=HEADERS,
            amc_slug=amc_slug
        )
        print(f"-> HTML Saved: {success}")
        
        if success:
            # Parse dynamic details and save processed JSON
            parsed_ok = DocumentParser.parse_and_save_json(
                raw_html_path=raw_html_path,
                processed_json_path=processed_json_path,
                scheme_name=scheme_name,
                amc_name=amc_name,
                url=url,
                category=category
            )
            print(f"-> Details Parsed and JSON Saved: {parsed_ok}")
        else:
            print("-> Skipping details extraction because crawl failed.")
        
    # 3. Read Processed JSON and Generate Logical Chunks
    chunks, chunk_metadatas, chunk_ids = DocumentChunker.compile_chunks_from_json(processed_dir)
    
    # 4. Vector Database Indexing
    if chunks:
        # Generate embeddings
        bge_embedding = BGEEmbeddingFunction(EMBEDDING_MODEL_NAME)
        embeddings = bge_embedding(chunks)
        
        # Save chunked data to chunks.json
        chunked_data = []
        for cid, text, meta in zip(chunk_ids, chunks, chunk_metadatas):
            chunked_data.append({
                "chunk_id": cid,
                "text": text,
                "source_url": meta.get("source_url"),
                "source_type": meta.get("source_type"),
                "amc": meta.get("amc"),
                "scheme_name": meta.get("scheme_name"),
                "scheme_category": meta.get("scheme_category"),
                "section_title": meta.get("section_title"),
                "page_number": meta.get("page_number"),
                "last_updated": meta.get("last_updated"),
                "content_hash": meta.get("content_hash")
            })
        
        chunks_json_path = run_dir / "chunks.json"
        try:
            with open(chunks_json_path, "w", encoding="utf-8") as f:
                json.dump(chunked_data, f, indent=2, ensure_ascii=False)
            print(f"--> Saved chunked data to: {chunks_json_path}")
        except Exception as e:
            print(f"--> Failed to save chunks.json: {e}")
            
        # Save embedding content to embeddings.json
        embeddings_data = []
        for cid, emb in zip(chunk_ids, embeddings):
            embeddings_data.append({
                "id": cid,
                "embedding": emb
            })
            
        embeddings_json_path = run_dir / "embeddings.json"
        try:
            with open(embeddings_json_path, "w", encoding="utf-8") as f:
                json.dump(embeddings_data, f, indent=2, ensure_ascii=False)
            print(f"--> Saved embedding content to: {embeddings_json_path}")
        except Exception as e:
            print(f"--> Failed to save embeddings.json: {e}")
            
        # Write to ChromaDB passing pre-computed embeddings
        DocumentIndexer.index_chunks(
            chunks=chunks,
            embeddings=embeddings,
            metadatas=chunk_metadatas,
            ids=chunk_ids,
            db_path=DB_DIR,
            collection_name=CHROMA_COLLECTION_NAME,
            model_name=EMBEDDING_MODEL_NAME
        )
        
        # 5. Clean up old runs directly under data/ to keep workspace tidy
        run_folders = [d for d in data_parent.iterdir() if d.is_dir() and d.name.startswith("run_")]
        for folder in run_folders:
            try:
                shutil.rmtree(folder)
                print(f"-> Cleaned up old run directory: {folder.name}")
            except Exception as e:
                print(f"-> Failed to delete old run directory {folder.name}: {e}")
                
        print("\nPackaged Ingestion Pipeline execution completed successfully!")
    else:
        print("\nWarning: No chunks compiled. Skipping vector database indexing.")

if __name__ == "__main__":
    run_ingestion()
