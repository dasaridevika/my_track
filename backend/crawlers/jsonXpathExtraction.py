import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonXPathExtractionStrategy
DEFAULT_XPATH_SCHEMA = {
    "name": "Generic XPath Extraction",
    "baseSelector": "//body",
    "fields": [
        {"name": "title", "selector": "//h1 | //h2", "type": "text"},
        {"name": "paragraph", "selector": "//p", "type": "text"},
        {"name": "link", "selector": "//a", "type": "attribute", "attribute": "href"}
    ]
}

async def xpath_extract(url: str, xpath_schema: dict | None = None, **kwargs):
    active_schema = xpath_schema if (isinstance(xpath_schema, dict) and xpath_schema) else DEFAULT_XPATH_SCHEMA
    strategy = JsonXPathExtractionStrategy(active_schema)
    try:
        async with AsyncWebCrawler() as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(
                    url=url,
                    extraction_strategy=strategy
                )
        return {
            "success": result.success,
            "url": result.url,
            "extracted_content": getattr(result, "extracted_content", None),
            "markdown": getattr(result, "markdown", ""),
            "metadata": getattr(result, "metadata", {}),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Crawler request timed out after 80 seconds."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Optional: Run this file directly for testing
if __name__ == "__main__":
    async def main():
        data = await xpath_extract("https://www.geeksforgeeks.org")
        print(json.dumps(data, indent=4, default=str))
    asyncio.run(main())
