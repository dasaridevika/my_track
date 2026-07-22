import asyncio
from crawl4ai import AsyncWebCrawler
async def crawl_single_page(url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        return {
            "success": result.success,
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