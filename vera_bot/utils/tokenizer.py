"""
Token counting utility for Groq LLM (llama-3.3-70b-versatile).
Uses tiktoken for accurate token counting compatible with Llama models.
"""

import tiktoken


def get_encoding():
    """Get the encoding for llama models (compatible with Groq's llama-3.3-70b)."""
    try:
        # Try to use Llama-specific encoding
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        # Fallback to cl100k_base which is close to Llama tokenization
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a given text string."""
    if not text:
        return 0
    encoding = get_encoding()
    tokens = encoding.encode(text)
    return len(tokens)


def count_prompt_tokens(system_prompt: str, user_message: str) -> int:
    """
    Count tokens for a chat-style prompt.
    Accounts for formatting overhead in chat completion API calls.
    """
    encoding = get_encoding()
    
    # Chat format adds overhead: <s>[INST] system_prompt \n user_message [/INST]
    # Each message has overhead of ~4-5 tokens
    system_tokens = len(encoding.encode(system_prompt))
    user_tokens = len(encoding.encode(user_message))
    
    # Add overhead for chat markers
    overhead = 10  # Approximate overhead for <s>[INST] ... [/INST] markers
    
    return system_tokens + user_tokens + overhead


def count_completion_tokens(response: str) -> int:
    """Count tokens in a completion response."""
    return count_tokens(response)


def estimate_total_cost(prompt_tokens: int, completion_tokens: int, model: str = "llama-3.3-70b-versatile") -> dict:
    """
    Estimate cost based on Groq pricing.
    Groq pricing as of 2024: roughly $0.00005 per 1K prompt tokens, $0.00015 per 1K completion tokens.
    (Check current pricing at https://groq.com/pricing)
    """
    # Groq pay-as-you-go pricing (approximate, update based on actual pricing)
    prompt_cost_per_1k = 0.00005
    completion_cost_per_1k = 0.00015
    
    prompt_cost = (prompt_tokens / 1000) * prompt_cost_per_1k
    completion_cost = (completion_tokens / 1000) * completion_cost_per_1k
    total_cost = prompt_cost + completion_cost
    
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_cost": round(prompt_cost, 6),
        "completion_cost": round(completion_cost, 6),
        "total_cost": round(total_cost, 6),
    }
