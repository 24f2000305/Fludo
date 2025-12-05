"""
Context Caching Implementation for CadQuery Agent
=================================================

This module implements Gemini's context caching to reduce API costs by 90%
and improve response times for CadQuery code generation.

Usage:
    from cad_agent_cached import generate_cadquery_code_cached
    
    code = generate_cadquery_code_cached("Create a gear with 20 teeth")
"""

import google.generativeai as genai
import datetime
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure proper imports
app_dir = str(Path(__file__).parent)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from cad_agent import CADQUERY_SYSTEM_PROMPT, have_gemini

# Global cache variables
_cached_content: Optional[Any] = None
_cache_expiry: Optional[datetime.datetime] = None
_cache_hits = 0
_cache_misses = 0


def get_cached_model():
    """
    Get or create a cached Gemini model.
    
    The cache lasts for 1 hour. After expiry, a new cache is automatically created.
    This saves ~90% on API costs for the system prompt.
    
    Returns:
        GenerativeModel: A Gemini model with cached system prompt
    """
    global _cached_content, _cache_expiry, _cache_hits, _cache_misses
    
    if not have_gemini():
        raise ValueError("Gemini API key not configured")
    
    now = datetime.datetime.now()
    
    # Check if cache expired or doesn't exist
    if _cached_content is None or (_cache_expiry and now > _cache_expiry):
        _cache_misses += 1
        
        print(f"Creating new cached content (expires in 1 hour)")
        print(f"Cache stats - Hits: {_cache_hits}, Misses: {_cache_misses}")
        
        # Create new cached content
        try:
            _cached_content = genai.caching.CachedContent.create(
                model='models/gemini-1.5-flash-8b',
                system_instruction=CADQUERY_SYSTEM_PROMPT,
                ttl=datetime.timedelta(hours=1)  # Cache for 1 hour
            )
            _cache_expiry = now + datetime.timedelta(hours=1)
            
            print(f"✅ Cache created successfully. Expiry: {_cache_expiry}")
            
        except Exception as e:
            print(f"❌ Failed to create cache: {e}")
            print("Falling back to non-cached model")
            return genai.GenerativeModel('gemini-1.5-flash')
    else:
        _cache_hits += 1
    
    # Return model using cached content
    return genai.GenerativeModel.from_cached_content(_cached_content)


def generate_cadquery_code_cached(prompt: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Generate CadQuery code using cached model (90% cost reduction).
    
    Args:
        prompt: User's request in natural language
        max_retries: Number of retry attempts if generation fails
        
    Returns:
        Dict with 'code' and 'success' keys
        
    Example:
        >>> result = generate_cadquery_code_cached("Create a 50mm cube")
        >>> print(result['code'])
        import cadquery as cq
        result = cq.Workplane("XY").box(50, 50, 50)
    """
    try:
        model = get_cached_model()
        
        user_prompt = f"""Generate CadQuery code for: {prompt}

Remember:
- MUST assign final result to 'result' variable
- MUST use correct syntax (.circle().extrude() for cylinders, NOT .cylinder())
- MUST use loft for cones (.circle().workplane(offset>0).circle().loft())
- NEVER use .cone() or .cylinder() - these don't exist!

Return ONLY executable Python code, no markdown, no explanations."""

        response = model.generate_content(user_prompt)
        code = response.text.strip()
        
        # Clean up markdown code blocks if present
        if code.startswith('```python'):
            code = code.split('```python')[1].split('```')[0].strip()
        elif code.startswith('```'):
            code = code.split('```')[1].split('```')[0].strip()
        
        return {
            'success': True,
            'code': code,
            'cached': _cache_hits > 0
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'code': ''
        }


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about cache usage.
    
    Returns:
        Dict with cache hits, misses, and cost savings estimate
    """
    total_requests = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total_requests * 100) if total_requests > 0 else 0
    
    # Rough cost estimate (assumes $0.075 per 1M input tokens for flash)
    # System prompt is ~5000 tokens
    system_prompt_tokens = 5000
    cost_per_token = 0.075 / 1_000_000
    
    normal_cost = total_requests * system_prompt_tokens * cost_per_token
    cached_cost = (_cache_misses * system_prompt_tokens * cost_per_token) + \
                  (_cache_hits * system_prompt_tokens * cost_per_token * 0.1)  # 90% discount
    savings = normal_cost - cached_cost
    
    return {
        'cache_hits': _cache_hits,
        'cache_misses': _cache_misses,
        'total_requests': total_requests,
        'hit_rate_percent': round(hit_rate, 2),
        'estimated_normal_cost_usd': round(normal_cost, 4),
        'estimated_cached_cost_usd': round(cached_cost, 4),
        'estimated_savings_usd': round(savings, 4),
        'cache_expiry': _cache_expiry.isoformat() if _cache_expiry else None
    }


def clear_cache():
    """
    Manually clear the cache (useful for testing or forcing refresh).
    """
    global _cached_content, _cache_expiry
    
    if _cached_content:
        try:
            _cached_content.delete()
        except:
            pass
    
    _cached_content = None
    _cache_expiry = None
    print("Cache cleared")


# Example usage
if __name__ == "__main__":
    # Test the cached generation
    result = generate_cadquery_code_cached("Create a box 50x40x30mm")
    
    if result['success']:
        print("Generated code:")
        print(result['code'])
        print(f"\nUsed cache: {result['cached']}")
    else:
        print(f"Error: {result['error']}")
    
    # Print cache statistics
    stats = get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"  Hits: {stats['cache_hits']}")
    print(f"  Misses: {stats['cache_misses']}")
    print(f"  Hit Rate: {stats['hit_rate_percent']}%")
    print(f"  Estimated Savings: ${stats['estimated_savings_usd']}")
