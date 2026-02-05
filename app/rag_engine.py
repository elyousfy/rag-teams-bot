"""
RAG Query Engine with hybrid search (vector + BM25).

Provides document retrieval and LLM-powered question answering
with conversation memory and citation support.
"""

import chromadb
from typing import Optional
from collections import deque

from llama_index.core import (
    VectorStoreIndex,
    Settings,
    get_response_synthesizer,
)
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from rank_bm25 import BM25Okapi

from app import config


# System prompt for hallucination guardrails
SYSTEM_PROMPT = """You are a helpful assistant that answers questions about company documents.

IMPORTANT RULES:
1. Only answer based on the provided context from company documents.
2. If the context does not contain information to answer the question, say: "I don't have information about this in the company documents."
3. Always cite your sources by mentioning the document name and page number when available.
4. Be concise and direct in your answers.
5. If asked about topics clearly outside company documents, politely redirect to your purpose.

Context from company documents:
{context_str}

Previous conversation:
{conversation_history}
"""


class ConversationMemory:
    """Simple conversation memory with fixed window size."""

    def __init__(self, max_size: int = config.CONVERSATION_MEMORY_SIZE):
        self.messages: deque = deque(maxlen=max_size * 2)  # user + assistant pairs

    def add_user_message(self, message: str):
        self.messages.append(f"User: {message}")

    def add_assistant_message(self, message: str):
        self.messages.append(f"Assistant: {message}")

    def get_history(self) -> str:
        if not self.messages:
            return "No previous conversation."
        return "\n".join(self.messages)

    def clear(self):
        self.messages.clear()


class HybridRetriever:
    """
    Hybrid retriever combining vector search and BM25 keyword search
    with Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, vector_retriever: VectorIndexRetriever, nodes: list, top_k: int = config.TOP_K):
        self.vector_retriever = vector_retriever
        self.top_k = top_k

        # Prepare BM25 index
        self.nodes = nodes
        self.node_texts = [node.get_content() for node in nodes]
        tokenized_corpus = [text.lower().split() for text in self.node_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def _bm25_retrieve(self, query: str, top_k: int) -> list[NodeWithScore]:
        """Retrieve using BM25 keyword matching."""
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(NodeWithScore(node=self.nodes[idx], score=scores[idx]))

        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[NodeWithScore],
        bm25_results: list[NodeWithScore],
        k: int = 60
    ) -> list[NodeWithScore]:
        """
        Combine results using Reciprocal Rank Fusion.
        RRF score = sum(1 / (k + rank)) across all result lists
        """
        node_scores: dict = {}
        node_map: dict = {}

        # Process vector results
        for rank, node_with_score in enumerate(vector_results):
            node_id = node_with_score.node.node_id
            rrf_score = 1 / (k + rank + 1)
            node_scores[node_id] = node_scores.get(node_id, 0) + rrf_score
            node_map[node_id] = node_with_score.node

        # Process BM25 results
        for rank, node_with_score in enumerate(bm25_results):
            node_id = node_with_score.node.node_id
            rrf_score = 1 / (k + rank + 1)
            node_scores[node_id] = node_scores.get(node_id, 0) + rrf_score
            node_map[node_id] = node_with_score.node

        # Sort by combined RRF score
        sorted_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)

        # Return top-k results
        results = []
        for node_id, score in sorted_nodes[:self.top_k]:
            results.append(NodeWithScore(node=node_map[node_id], score=score))

        return results

    def retrieve(self, query: str) -> list[NodeWithScore]:
        """Perform hybrid retrieval."""
        # Get vector search results
        vector_results = self.vector_retriever.retrieve(query)

        # Get BM25 results
        bm25_results = self._bm25_retrieve(query, self.top_k * 2)

        # Combine with RRF
        combined = self._reciprocal_rank_fusion(vector_results, bm25_results)

        return combined


class RAGEngine:
    """
    Main RAG engine for querying company documents.
    """

    def __init__(self):
        self._index: Optional[VectorStoreIndex] = None
        self._query_engine = None
        self._hybrid_retriever: Optional[HybridRetriever] = None
        self._conversations: dict[str, ConversationMemory] = {}

    def initialize(self):
        """Initialize the RAG engine with models and index."""
        # Configure LLM
        llm = Ollama(
            model=config.OLLAMA_LLM_MODEL,
            base_url=config.OLLAMA_HOST,
            request_timeout=120.0,
        )
        Settings.llm = llm

        # Configure embedding model
        embed_model = OllamaEmbedding(
            model_name=config.OLLAMA_EMBED_MODEL,
            base_url=config.OLLAMA_HOST,
        )
        Settings.embed_model = embed_model

        # Load ChromaDB index
        chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))

        try:
            chroma_collection = chroma_client.get_collection("company_docs")
        except ValueError:
            raise RuntimeError(
                "No document collection found. Run 'python scripts/ingest.py' first."
            )

        if chroma_collection.count() == 0:
            raise RuntimeError(
                "Document collection is empty. Add documents and run ingestion."
            )

        # Create vector store and index
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        self._index = VectorStoreIndex.from_vector_store(vector_store)

        # Get all nodes for BM25
        # Note: This loads nodes from the vector store
        vector_retriever = VectorIndexRetriever(
            index=self._index,
            similarity_top_k=config.TOP_K * 2,
        )

        # For BM25, we need to get all documents from ChromaDB
        # Note: This loads all documents into memory for BM25 indexing.
        # For large corpora (10k+ chunks), consider disabling BM25 or using external search.
        all_docs = chroma_collection.get(include=["documents", "metadatas"])
        all_nodes = []
        for i, (doc_text, metadata) in enumerate(zip(all_docs["documents"], all_docs["metadatas"])):
            node = TextNode(text=doc_text, metadata=metadata or {})
            node.id_ = all_docs["ids"][i]
            all_nodes.append(node)

        # Create hybrid retriever
        self._hybrid_retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            nodes=all_nodes,
            top_k=config.TOP_K,
        )

        # Create response synthesizer
        self._response_synthesizer = get_response_synthesizer(
            response_mode="compact",
        )

    def get_conversation(self, user_id: str) -> ConversationMemory:
        """Get or create conversation memory for a user."""
        if user_id not in self._conversations:
            self._conversations[user_id] = ConversationMemory()
        return self._conversations[user_id]

    def clear_conversation(self, user_id: str):
        """Clear conversation history for a user and remove from memory."""
        self._conversations.pop(user_id, None)

    def query(self, question: str, user_id: str) -> dict:
        """
        Query the RAG system.

        Args:
            question: The user's question
            user_id: Unique identifier for conversation tracking

        Returns:
            dict with 'answer', 'sources', and 'chunks' keys
        """
        if not self._hybrid_retriever:
            raise RuntimeError("RAG engine not initialized. Call initialize() first.")

        # Get conversation memory
        conversation = self.get_conversation(user_id)

        # Retrieve relevant chunks
        retrieved_nodes = self._hybrid_retriever.retrieve(question)

        if not retrieved_nodes:
            return {
                "answer": "I couldn't find any relevant information in the company documents.",
                "sources": [],
                "chunks": [],
            }

        # Build context from retrieved chunks
        context_parts = []
        sources = []
        chunks = []

        for i, node_with_score in enumerate(retrieved_nodes):
            node = node_with_score.node
            text = node.get_content()
            metadata = node.metadata

            # Extract source info
            file_name = metadata.get("file_name", "Unknown document")
            page_num = metadata.get("page_label", metadata.get("page_num", ""))

            source_info = file_name
            if page_num:
                source_info += f" (page {page_num})"

            context_parts.append(f"[Source {i+1}: {source_info}]\n{text}")
            sources.append(source_info)
            chunks.append({
                "text": text[:200] + "..." if len(text) > 200 else text,
                "source": source_info,
                "score": node_with_score.score,
            })

        context_str = "\n\n".join(context_parts)

        # Build prompt with system instructions
        full_prompt = SYSTEM_PROMPT.format(
            context_str=context_str,
            conversation_history=conversation.get_history(),
        )

        # Query the LLM
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=full_prompt),
            ChatMessage(role=MessageRole.USER, content=question),
        ]

        response = Settings.llm.chat(messages)
        answer = response.message.content

        # Update conversation memory
        conversation.add_user_message(question)
        conversation.add_assistant_message(answer)

        return {
            "answer": answer,
            "sources": list(set(sources)),  # Unique sources
            "chunks": chunks,
        }


# Global RAG engine instance
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get the global RAG engine instance."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
        _rag_engine.initialize()
    return _rag_engine
