import os
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

WORKER_ANALYZE_URL = os.getenv(
    "LLM_ANALYSIS_URL",
    "https://shrill-smoke-7541.devika-worker.workers.dev/analyze"
).strip()


def extract_text_for_llm(result: dict) -> str:
    if not result or not isinstance(result, dict):
        return ""

    if "files" in result:
        return ""

    if any(key in result for key in ["screenshot", "pdf", "mhtml"]):
        return ""

    for key in ["text", "content", "markdown", "data", "result", "extracted_text"]:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


async def analyze_extracted_data(
    url: str,
    title: str,
    extracted_text: str,
    analysis_type: str = "summary"
):
    cleaned_text = (extracted_text or "").strip()
    if not cleaned_text:
        raise ValueError("No extracted text available for LLM analysis.")

    payload = {
        "url": url,
        "title": title,
        "text": cleaned_text,
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
                logger.warning(f"Rate limited by Worker. Waiting {wait_time}s before retry.")
                await asyncio.sleep(wait_time)
                delay *= 2
                continue

            error_body = response.text
            raise Exception(
                f"LLM analysis failed with status {response.status_code}: {error_body}"
            )

    raise Exception("LLM analysis failed after multiple retries due to rate limiting.")
