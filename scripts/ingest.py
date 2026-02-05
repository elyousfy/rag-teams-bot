#!/usr/bin/env python3
"""
Document ingestion script for the RAG system.

Processes documents from the documents folder and stores embeddings in ChromaDB.
Supports: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Markdown, Text files.

Usage:
    python scripts/ingest.py [--clear]

Options:
    --clear     Clear existing collection before ingestion
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from app import config


def setup_embedding_model():
    """Configure the embedding model."""
    return OllamaEmbedding(
        model_name=config.OLLAMA_EMBED_MODEL,
        base_url=config.OLLAMA_HOST,
    )


def load_documents(documents_path: Path) -> list:
    """Load documents from the specified directory."""
    if not documents_path.exists():
        print(f"Creating documents directory: {documents_path}")
        documents_path.mkdir(parents=True, exist_ok=True)
        return []

    # Supported file extensions
    supported_extensions = [
        ".pdf", ".docx", ".xlsx", ".pptx",
        ".md", ".txt", ".json", ".csv"
    ]

    # Check if there are any documents
    doc_files = []
    for ext in supported_extensions:
        doc_files.extend(documents_path.glob(f"**/*{ext}"))

    if not doc_files:
        print(f"No documents found in {documents_path}")
        print(f"Supported formats: {', '.join(supported_extensions)}")
        return []

    print(f"Found {len(doc_files)} document(s) to process:")
    for f in doc_files:
        print(f"  - {f.name}")

    # Load documents
    reader = SimpleDirectoryReader(
        input_dir=str(documents_path),
        recursive=True,
        required_exts=supported_extensions,
    )

    documents = reader.load_data()
    print(f"Loaded {len(documents)} document section(s)")

    return documents


def create_nodes(documents: list) -> list:
    """Split documents into chunks/nodes."""
    splitter = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )

    nodes = splitter.get_nodes_from_documents(documents, show_progress=True)
    print(f"Created {len(nodes)} chunks")

    return nodes


def setup_vector_store(clear: bool = False) -> tuple:
    """Set up ChromaDB vector store. Returns (vector_store, existing_count)."""
    chroma_path = config.CHROMA_PATH
    chroma_path.mkdir(parents=True, exist_ok=True)

    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path=str(chroma_path))

    collection_name = "company_docs"

    if clear:
        # Delete existing collection if it exists
        try:
            chroma_client.delete_collection(collection_name)
            print(f"Cleared existing collection: {collection_name}")
        except ValueError:
            pass  # Collection doesn't exist

    # Get or create collection
    chroma_collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    existing_count = chroma_collection.count()
    print(f"Collection '{collection_name}' has {existing_count} existing documents")

    # Create vector store
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    return vector_store, existing_count


def ingest_documents(clear: bool = False):
    """Main ingestion pipeline."""
    print("=" * 60)
    print("RAG Document Ingestion")
    print("=" * 60)

    # Setup embedding model in Settings
    print("\n1. Setting up embedding model...")
    embed_model = setup_embedding_model()
    Settings.embed_model = embed_model

    # Load documents
    print("\n2. Loading documents...")
    documents = load_documents(config.DOCUMENTS_PATH)

    if not documents:
        print("\nNo documents to process. Add documents to:")
        print(f"  {config.DOCUMENTS_PATH}")
        return

    # Create nodes/chunks
    print("\n3. Chunking documents...")
    nodes = create_nodes(documents)

    # Setup vector store
    print("\n4. Setting up vector store...")
    vector_store, existing_count = setup_vector_store(clear=clear)

    # Warn about potential duplicates
    if existing_count > 0 and not clear:
        print("\n" + "!" * 60)
        print("WARNING: Collection already contains documents!")
        print("Running without --clear will ADD duplicates.")
        print("Use 'python scripts/ingest.py --clear' to replace existing data.")
        print("!" * 60)
        response = input("\nContinue anyway? [y/N]: ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Create index and embed nodes
    print("\n5. Creating embeddings and storing in ChromaDB...")
    print("   (This may take a while depending on document size)")

    index = VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print(f"Processed {len(documents)} document section(s)")
    print(f"Created {len(nodes)} chunks")
    print(f"Stored in: {config.CHROMA_PATH}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into the RAG system"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collection before ingestion"
    )

    args = parser.parse_args()

    try:
        ingest_documents(clear=args.clear)
    except Exception as e:
        print(f"\nError during ingestion: {e}")
        raise


if __name__ == "__main__":
    main()
