import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import RegexExtractionStrategy
patterns = {
    "emails": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phones": r"\+?\d[\d\s()-]{8,}\d",
    "dates": r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",
    "urls": r"https?://[^\s\"'>]+"
}
async def regex_extract(url: str):
    strategy = RegexExtractionStrategy(patterns=patterns)

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
        data = await regex_extract("https://www.geeksforgeeks.org")
        print(json.dumps(data, indent=4, default=str))
    asyncio.run(main())