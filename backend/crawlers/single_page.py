import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig

async def crawl_single_page(url: str):
    run_config = CrawlerRunConfig()

    async with AsyncWebCrawler() as crawler:
        async with asyncio.timeout(80):
            result = await crawler.arun(url=url, config=run_config)

    if not result.success:
        return {
            "success": False,
            "url": url,
            "error": getattr(result, "error_message", "Crawl failed")
        }

    return {
        "success": True,
        "url": url,
        "markdown": result.markdown,
        "html": result.html,
        "links": result.links,
        "media": result.media,
        "metadata": result.metadata,
    }

if __name__ == "__main__":
    async def main():
        data = await crawl_single_page("https://www.geeksforgeeks.org")
        print(data)

    asyncio.run(main())
