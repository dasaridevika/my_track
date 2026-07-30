import re
import json
import asyncio
import logging
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import RegexExtractionStrategy

logger = logging.getLogger(__name__)

DEFAULT_PATTERNS = {
    "emails": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phones": r"\+?\d{1,4}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
    "dates": r"\b\d{4}[-/.]\d{2}[-/.]\d{2}\b|\b\d{2}[-/.]\d{2}[-/.]\d{4}\b",
    "urls": r"https?://[^\s\"'<>]+",
}


def parse_patterns_input(patterns_input) -> dict:
    if not patterns_input:
        return DEFAULT_PATTERNS.copy()
    if isinstance(patterns_input, dict):
        return patterns_input
    if isinstance(patterns_input, str):
        patterns_str = patterns_input.strip()
        if not patterns_str:
            return DEFAULT_PATTERNS.copy()
        try:
            parsed = json.loads(patterns_str)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        parsed_dict = {}
        for line in patterns_str.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                key, pat = line.split(":", 1)
                parsed_dict[key.strip()] = pat.strip()
            else:
                parsed_dict[f"pattern_{len(parsed_dict)+1}"] = line
        return parsed_dict if parsed_dict else DEFAULT_PATTERNS.copy()
    return DEFAULT_PATTERNS.copy()


def fallback_regex_extract(text: str, patterns: dict, source_url: str) -> list:
    if not text:
        return []
    matches = []
    seen = set()
    for label, pat in patterns.items():
        try:
            compiled = re.compile(pat)
            for m in compiled.finditer(text):
                val = m.group(0).strip()
                if not val or len(val) < 2:
                    continue
                key = (label, val)
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "url": source_url,
                        "label": label,
                        "value": val,
                        "span": [m.start(), m.end()],
                    })
        except Exception as err:
            logger.warning(f"Invalid regex pattern '{pat}' for label '{label}': {err}")
    return matches[:100]


async def regex_extract(url: str, regex_patterns: dict | str | None = None, **kwargs):
    active_patterns = parse_patterns_input(regex_patterns)
    strategy = RegexExtractionStrategy(custom=active_patterns)
    config = CrawlerRunConfig(extraction_strategy=strategy)

    try:
        async with AsyncWebCrawler() as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(url=url, config=config)

        extracted_content = getattr(result, "extracted_content", None)
        parsed = None

        if isinstance(extracted_content, str) and extracted_content.strip():
            try:
                parsed = json.loads(extracted_content)
            except Exception:
                parsed = None

        # Fallback if Crawl4AI extraction strategy returned empty list or None
        if not parsed or (isinstance(parsed, list) and len(parsed) == 0):
            logger.info("Crawl4AI regex strategy returned empty; running fallback regex matcher on page content")
            page_text = getattr(result, "markdown", "") or getattr(result, "html", "")
            matches = fallback_regex_extract(page_text, active_patterns, url)
            extracted_content = json.dumps(matches, indent=2, ensure_ascii=False)

        return {
            "success": getattr(result, "success", False),
            "url": getattr(result, "url", url),
            "extracted_content": extracted_content,
            "markdown": getattr(result, "markdown", ""),
            "metadata": getattr(result, "metadata", {}),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Regex extraction request timed out after 80 seconds."
        }
    except Exception as e:
        logger.exception("Regex extraction failed")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    async def main():
        data = await regex_extract("https://www.geeksforgeeks.org")
        print(json.dumps(data, indent=4, default=str))

    asyncio.run(main())

