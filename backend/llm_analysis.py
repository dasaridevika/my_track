import os
import asyncio
import logging
import httpx
logger = logging.getLogger(__name__)
WORKER_ANALYZE_URL = os.getenv(
    "LLM_ANALYSIS_URL",
    "https://shrill-smoke-7541.devika-worker.workers.dev"
).strip()
def extract_text_for_llm(result: dict) -> str:
    if not result or not isinstance(result, dict):
        return ""
    # Skip binary/file responses
    if "files" in result:
        return ""
    if any(key in result for key in ["screenshot", "pdf", "mhtml"]):
        return ""
    # -------- Normal methods --------
    for key in ["text", "content", "markdown", "result", "extracted_text"]:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # -------- Deep Crawl --------
    data = result.get("data")
    if isinstance(data, dict):
        for key in ["markdown", "text", "content"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    # -------- Dynamic Crawl --------
    pages = result.get("pages")
    if isinstance(pages, list):
        extracted = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            for key in ["markdown", "text", "content"]:
                value = page.get(key)
                if isinstance(value, str) and value.strip():
                    extracted.append(value.strip())
                    break
        if extracted:
            return "\n\n".join(extracted)
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
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(WORKER_ANALYZE_URL, json=payload)
        if response.status_code == 200:
            return response.json()
        error_body = response.text
        raise Exception(
            f"LLM analysis failed with status {response.status_code}: {error_body}"
        )
