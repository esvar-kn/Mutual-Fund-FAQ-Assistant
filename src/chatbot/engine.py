import os
from groq import Groq
from pathlib import Path

# Try-except absolute/local import for configuration resilience
try:
    from src.config import GROQ_MODEL
except ModuleNotFoundError:
    import sys
    current_dir = Path(__file__).resolve().parent
    sys.path.append(str(current_dir.parent.parent))
    sys.path.append(str(current_dir.parent))
    
    try:
        from src.config import GROQ_MODEL
    except ModuleNotFoundError:
        GROQ_MODEL = "llama-3.1-8b-instant"

class GroqChatEngine:
    """Handles system prompt construction and Groq LLM completion requests."""
    def __init__(self, api_key=None):
        # Fallback to env variable if key is not passed
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("Warning: GROQ_API_KEY is not set. LLM generation calls will fail.")
        self.client = Groq(api_key=self.api_key)

    def generate_answer(self, query, contexts):
        """Constructs prompt context and queries Groq LLM model."""
        # 1. Format Context Blocks
        context_str = ""
        for i, ctx in enumerate(contexts):
            context_str += f"Context Block {i+1} (Source: {ctx['source_url']}):\n{ctx['text']}\n\n"

        # 2. System Instructions
        system_instruction = (
            "You are a facts-only Mutual Fund FAQ Assistant.\n"
            "You answer queries about mutual fund schemes using ONLY the provided Context Blocks.\n\n"
            "RULES:\n"
            "1. Your response must be extremely concise and MUST NOT exceed 3 sentences in total.\n"
            "2. Cite exactly ONE relevant source URL from the provided Context Blocks at the end.\n"
            "3. Do not offer opinions, financial advice, projections, or suggestions. Be objective.\n"
            "4. If performance returns are asked, do not calculate or compare returns. Refer to the factsheet link.\n"
            "5. If the details are not present in the context, state: \"I do not have access to official documents containing that information.\" and do not make up details.\n\n"
            "Format your output EXACTLY as follows:\n"
            "Answer: <your factual answer in 1-3 sentences>\n"
            "Source: <single source_url>"
        )

        user_prompt = f"Context:\n{context_str}\nQuery:\n{query}"

        # 3. Call Groq Completion
        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.0, # Zero temperature for max factual consistency
            max_tokens=250
        )

        return chat_completion.choices[0].message.content.strip()

    def generate_corrected_answer(self, query, raw_response, contexts):
        """Constructs a correction prompt requesting Groq LLM to rewrite the response to strictly 1-3 sentences."""
        context_str = ""
        for i, ctx in enumerate(contexts):
            context_str += f"Context Block {i+1} (Source: {ctx['source_url']}):\n{ctx['text']}\n\n"

        system_instruction = (
            "You are a facts-only Mutual Fund FAQ Assistant.\n"
            "Your previous response violated the strict sentence count limit (more than 3 sentences). "
            "Please rewrite the previous response to be extremely concise and exactly 1 to 3 sentences in total.\n"
            "Cite exactly ONE relevant source URL from the provided Context Blocks at the end.\n"
            "Do not make up facts. Maintain objective, facts-only tone. You answer queries using ONLY the provided Context Blocks.\n\n"
            "Format your output EXACTLY as follows:\n"
            "Answer: <your factual answer in 1-3 sentences>\n"
            "Source: <single source_url>"
        )

        user_prompt = (
            f"Context:\n{context_str}\n"
            f"Original Query:\n{query}\n"
            f"Previous Violating Response:\n{raw_response}\n"
            f"Please rewrite the previous violating response to make it extremely concise and exactly 1-3 sentences."
        )

        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.0,
            max_tokens=250
        )

        return chat_completion.choices[0].message.content.strip()
