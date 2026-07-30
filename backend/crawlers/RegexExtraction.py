import json
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import RegexExtractionStrategy

DEFAULT_PATTERNS = {
    "emails": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phones": r"\+?\d[\d\s()-]{8,}\d",
    "dates": r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",
    "urls": r"https?://[^\s\"'>]+",
}

async def regex_extract(url: str, regex_patterns: dict | None = None, **kwargs):
    active_patterns = regex_patterns if (isinstance(regex_patterns, dict) and regex_patterns) else DEFAULT_PATTERNS
    strategy = RegexExtractionStrategy(custom=active_patterns)
    config = CrawlerRunConfig(extraction_strategy=strategy)

    try:
        async with AsyncWebCrawler() as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(url=url, config=config)

        return {
            "success": getattr(result, "success", False),
            "url": getattr(result, "url", url),
            "extracted_content": getattr(result, "extracted_content", None),
            "markdown": getattr(result, "markdown", ""),
            "metadata": getattr(result, "metadata", {}),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Regex extraction request timed out after 80 seconds."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    async def main():
        data = await regex_extract("https://www.geeksforgeeks.org")
        print(json.dumps(data, indent=4, default=str))

    asyncio.run(main())
