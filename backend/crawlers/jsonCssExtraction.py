import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
schema = {
    "name": "Example Page",
    "baseSelector": "body",
    "fields": [
        {
            "name": "title",
            "selector": "h1",
            "type": "text"
        },
        {
            "name": "paragraph",
            "selector": "p",
            "type": "text"
        },
        {
            "name": "link",
            "selector": "a",
            "type": "attribute",
            "attribute": "href"
        }
    ]
}
async def css_extract(url: str):
    strategy = JsonCssExtractionStrategy(schema)
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
            "markdown": result.markdown,
            "html": result.html,
            "extracted_content": result.extracted_content,
            "metadata": result.metadata,
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Crawler request timed out after 80 seconds."
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
