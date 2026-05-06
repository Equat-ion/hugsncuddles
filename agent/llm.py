from functools import lru_cache
from openai import AsyncOpenAI
from api.settings import settings


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


async def call_llm(
    prompt: str,
    system: str,
    model: str | None = None,
    tools: list | None = None,
    response_format: dict | None = None,
) -> str:
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        tools=tools,
        response_format=response_format,
        max_tokens=settings.llm_max_tokens,
    )
    return resp.choices[0].message.content
