#!/usr/bin/env python3
"""
Test script for the RAG engine.

Usage:
    python scripts/test_rag.py
    python scripts/test_rag.py "Your question here"
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rag():
    """Test the RAG engine with sample queries."""
    from app.rag_engine import get_rag_engine

    print("Initializing RAG engine...")
    try:
        engine = get_rag_engine()
    except RuntimeError as e:
        print(f"Error: {e}")
        print("\nMake sure to run 'python scripts/ingest.py' first.")
        return

    print("RAG engine initialized successfully!\n")

    # Test queries
    test_questions = [
        "What is the remote work policy?",
        "How many days of PTO do employees get?",
        "What are the password requirements?",
        "What is the hotel reimbursement limit?",
    ]

    # If command line argument provided, use that instead
    if len(sys.argv) > 1:
        test_questions = [" ".join(sys.argv[1:])]

    user_id = "test-user"

    for question in test_questions:
        print("=" * 60)
        print(f"Question: {question}")
        print("-" * 60)

        result = engine.query(question, user_id)

        print(f"\nAnswer:\n{result['answer']}")

        if result['sources']:
            print(f"\nSources: {', '.join(result['sources'])}")

        print()

    print("=" * 60)
    print("Test complete!")


def interactive_mode():
    """Run in interactive mode."""
    from app.rag_engine import get_rag_engine

    print("Initializing RAG engine...")
    try:
        engine = get_rag_engine()
    except RuntimeError as e:
        print(f"Error: {e}")
        print("\nMake sure to run 'python scripts/ingest.py' first.")
        return

    print("RAG engine ready! Type 'quit' to exit.\n")

    user_id = "interactive-user"

    while True:
        try:
            question = input("You: ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if question.lower() == '/clear':
                engine.clear_conversation(user_id)
                print("Conversation cleared.\n")
                continue

            result = engine.query(question, user_id)

            print(f"\nBot: {result['answer']}")

            if result['sources']:
                print(f"\n[Sources: {', '.join(result['sources'])}]")

            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        test_rag()
