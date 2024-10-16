import asyncio
from openai import OpenAI
from config import GITHUB_TOKEN, AI_BASE_URL

client = OpenAI(
    base_url=AI_BASE_URL,
    api_key=GITHUB_TOKEN,
)

async def get_ai_response(user_message):
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            top_p=1
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Error getting AI response: {e}")
