import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
DEFAULT_SCHEMA = {
    "name": "Generic CSS Extraction",
    "baseSelector": "body",
    "fields": [
        {"name": "title", "selector": "h1, h2", "type": "text"},
        {"name": "paragraphs", "selector": "p", "type": "text"},
        {"name": "links", "selector": "a", "type": "attribute", "attribute": "href"}
    ]
}

async def css_extract(url: str, css_schema: dict | None = None, **kwargs):
    active_schema = css_schema if (isinstance(css_schema, dict) and css_schema) else DEFAULT_SCHEMA
    strategy = JsonCssExtractionStrategy(active_schema)
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
            "markdown": getattr(result, "markdown", ""),
            "html": getattr(result, "html", ""),
            "extracted_content": getattr(result, "extracted_content", None),
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
        data = await css_extract("https://www.geeksforgeeks.org")
        print(json.dumps({
            "success": data["success"],
            "url": data.get("url"),
            "extracted_content": data.get("extracted_content"),
            "error": data.get("error")
        }, indent=4, default=str))
    asyncio.run(main())
