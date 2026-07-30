import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

run_config = CrawlerRunConfig()
browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,
    ignore_https_errors=True,
    extra_args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--js-flags=--max-old-space-size=128"
    ]
)


async def crawl_single_page(url: str, **kwargs):
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(
                    url=url,
                    config=run_config
                )
        md = getattr(result, "markdown", "")
        if hasattr(md, "fit_markdown"):
            md = md.fit_markdown or md.raw_markdown or str(md)
        return {
            "success": getattr(result, "success", False),
            "url": url,
            "markdown": str(md or ""),
            "html": getattr(result, "html", ""),
            "links": getattr(result, "links", {}),
            "media": getattr(result, "media", {}),
            "metadata": getattr(result, "metadata", {}),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "url": url,
            "error": "Single page crawl timed out after 80 seconds."
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e)
        }


if __name__ == "__main__":
    async def main():
        data = await crawl_single_page("https://www.geeksforgeeks.org")
        print(data)

    asyncio.run(main())
