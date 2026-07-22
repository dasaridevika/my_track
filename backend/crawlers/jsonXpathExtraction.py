import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonXPathExtractionStrategy
schema = {
    "name": "Example Page",
    "baseSelector": "/html/body",
    "fields": [
        {
            "name": "title",
            "selector": "//h1",
            "type": "text"
        },
        {
            "name": "paragraph",
            "selector": "//p",
            "type": "text"
        },
        {
            "name": "link",
            "selector": "//a",
            "type": "attribute",
            "attribute": "href"
        }
    ]
}
async def xpath_extract(url: str):
    strategy = JsonXPathExtractionStrategy(schema)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            extraction_strategy=strategy
        )
    return {
        "success": result.success,
        "url": result.url,
        "extracted_content": result.extracted_content,
        "markdown": result.markdown,
        "metadata": result.metadata,
    }
# Optional: Run this file directly for testing
if __name__ == "__main__":
    import asyncio
    async def main():
        data = await xpath_extract("https://www.geeksforgeeks.org")
        print(json.dumps(data, indent=4, default=str))
    asyncio.run(main())