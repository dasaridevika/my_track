import os
import asyncio
import logging
import httpx
import re
import json
logger = logging.getLogger(__name__)
WORKER_ANALYZE_URL = os.getenv(
    "LLM_ANALYSIS_URL",
    "https://shrill-smoke-7541.devika-worker.workers.dev"
).strip()
def extract_text_for_llm(result: dict) -> str:
    if not result or not isinstance(result, dict):
        return ""
        
    # -------- 1. Direct result keys --------
    for key in ["extracted_content", "text", "content", "markdown", "result", "extracted_text"]:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        elif value and not isinstance(value, (str, bool, int, float)):
            # Convert list/dict (e.g. JSON CSS extraction results) to formatted JSON string
            try:
                return json.dumps(value, indent=2)
            except Exception:
                pass

    # -------- 2. Deep Crawl (nested under data) --------
    data = result.get("data")
    if isinstance(data, dict):
        # Check if deep crawl HTML format (contains data -> pages list)
        pages = data.get("pages")
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
                
        # Check standard data keys (e.g. docx, txt, pdf)
        for key in ["text", "content", "markdown"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            elif value and not isinstance(value, (str, bool, int, float)):
                try:
                    return json.dumps(value, indent=2)
                except Exception:
                    pass

    # -------- 3. Dynamic Crawl (direct pages list) --------
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
def clean_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. Remove HTML tags if any are present
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. Remove markdown images ![alt text](url) completely
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    
    # 3. Replace markdown links [text](url) with just the text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 4. Remove inline URLs (http/https links) that are just standing alone
    text = re.sub(r'https?://\S+', '', text)
    
    # 5. Split into lines and filter out boilerplate lines
    lines = text.split('\n')
    cleaned_lines = []
    
    # Boilerplate patterns to drop (navigation, footers, headers, social)
    boilerplate_patterns = [
        r'.*privacy\s*policy.*',
        r'.*terms\s*of\s*(?:service|use).*',
        r'.*all\s*rights\s*reserved.*',
        r'.*copyright\s*(?:©|c|\(c\))?\s*\d{4}.*',
        r'.*cookie\s*policy.*',
        r'.*contact\s*us.*',
        r'.*about\s*us.*',
        r'.*careers.*',
        r'.*help\s*&\s*support.*',
        r'^\s*sign\s*in\s*/\s*register\s*$',
        r'^\s*login\s*$',
        r'^\s*sign\s*up\s*$',
        r'^\s*forgot\s*password\s*$',
        r'^\s*skip\s*to\s*content\s*$',
        r'^\s*navigation\s*$',
        r'^\s*menu\s*$',
        r'^#+\s*navigation\s*$',
        r'^#+\s*menu\s*$',
    ]
    
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in boilerplate_patterns]
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Skip lines that match boilerplate patterns (only for short lines to avoid false positives in body text)
        if len(stripped) < 80:
            if any(pattern.match(stripped) for pattern in compiled_patterns):
                continue
            
        # Skip line if it only consists of special characters/punctuation (dividers)
        if re.match(r'^[_\-\*\=\#\s\d\|\|]+$', stripped) and len(stripped) > 2:
            continue
            
        cleaned_lines.append(stripped)
        
    text = '\n'.join(cleaned_lines)
    
    # Normalize whitespace (remove multiple empty lines, keep spacing clean)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def parse_llm_response(response_json: dict) -> dict:
    if not response_json or not isinstance(response_json, dict):
        return {"summary": str(response_json)}
        
    result = response_json.get("result", {})
    if not isinstance(result, dict):
        return {"summary": str(result)}
        
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        return {"summary": str(response_json)}
        
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        return {"summary": str(response_json)}
        
    # Try to parse the inner JSON string
    try:
        parsed_content = json.loads(content)
        if isinstance(parsed_content, dict):
            return parsed_content
    except Exception:
        pass
        
    return {"summary": content}

async def analyze_extracted_data(
    url: str,
    title: str,
    extracted_text: str,
    analysis_type: str = "summary"
):
    if not extracted_text or not extracted_text.strip():
        raise ValueError("No extracted text available for LLM analysis.")
        
    raw_len = len(extracted_text)
    cleaned_text = clean_text(extracted_text)
    
    # Fallback to raw if cleaning filters out everything
    if not cleaned_text.strip():
        cleaned_text = extracted_text.strip()
        
    cleaned_len = len(cleaned_text)
    logger.info(f"LLM analysis context compression: {raw_len} chars -> {cleaned_len} chars ({((raw_len-cleaned_len)/raw_len)*100:.1f}% reduction)")
    
    payload = {
        "url": url,
        "title": title,
        "text": cleaned_text,
        "analysis_type": analysis_type
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(WORKER_ANALYZE_URL, json=payload)
        if response.status_code == 200:
            parsed_data = parse_llm_response(response.json())
            return parsed_data
        error_body = response.text
        raise Exception(
            f"LLM analysis failed with status {response.status_code}: {error_body}"
        )
