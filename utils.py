from cachetools import TTLCache, LRUCache

def create_message_cache():
    return TTLCache(maxsize=10000, ttl=3600)  # Increased cache size and TTL

response_cache = LRUCache(maxsize=1000)  # Add this line

def get_cache_key(chat_id, user_message):
    return f"{chat_id}:{user_message}"

def update_cache(bot_data, cache_key, ai_response):
    if 'message_cache' not in bot_data:
        bot_data['message_cache'] = create_message_cache()
    bot_data['message_cache'][cache_key] = ai_response
    response_cache[cache_key] = ai_response  # Add this line

def get_cached_response(cache_key):
    return response_cache.get(cache_key)  # Add this function
