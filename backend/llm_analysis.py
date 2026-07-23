import httpx

WORKER_ANALYZE_URL = "https://shrill-smoke-7541.devika-worker.workers.dev/analyze"

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

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(WORKER_ANALYZE_URL, json=payload)
        response.raise_for_status()
        return response.json()
