import asyncio
import httpx

WORKER_ANALYZE_URL = "https://shrill-smoke-7541.devika-worker.workers.dev"

def extract_text_for_llm(result: dict) -> str:
    for key in ["text", "content", "markdown", "data", "result"]:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return str(result)

async def analyze_extracted_data(url: str, title: str, extracted_text: str, analysis_type: str = "summary"):
    payload = {
        "url": url,
        "title": title,
        "extracted_text": extracted_text,
        "analysis_type": analysis_type
    }

    retries = 3
    delay = 2

    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(retries):
            response = await client.post(WORKER_ANALYZE_URL, json=payload)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else delay
                await asyncio.sleep(wait_time)
                delay *= 2
                continue

            response.raise_for_status()

    raise Exception("LLM analysis failed after multiple retries due to rate limiting.")
