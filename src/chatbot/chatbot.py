import os
from dotenv import load_dotenv

from src.chatbot.retriever import MutualFundRetriever
from src.chatbot.engine import GroqChatEngine

def run_chatbot_test():
    load_dotenv()
    
    print("\n--- Verifying Packaged Chatbot Components locally ---")
    retriever = MutualFundRetriever()
    
    # Test retrieval
    test_query = "What is the exit load for HDFC Mid-Cap opportunities Fund?"
    print(f"\nQuery: {test_query}")
    matches = retriever.retrieve_context(test_query, top_k=2)
    for m in matches:
        print(f"\nRetrieved Chunk from {m['scheme_name']}:")
        print(f"Text: {m['text'][:120]}...")
        print(f"URL: {m['source_url']} | Score (distance): {m['distance']}")

    # Test LLM Call if API key is set
    if os.getenv("GROQ_API_KEY"):
        print("\nGROQ API Key found. Triggering test answer generation...")
        engine = GroqChatEngine()
        answer = engine.generate_answer(test_query, matches)
        print("\nGenerated Chat Output:")
        print(answer)
    else:
        print("\nSkipping LLM call because GROQ_API_KEY is not configured in env.")

if __name__ == "__main__":
    run_chatbot_test()
