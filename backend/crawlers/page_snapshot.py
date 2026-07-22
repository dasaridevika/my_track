import os
import base64

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)


async def page_snapshot(url: str):
    # Create output directory
    os.makedirs("outputs", exist_ok=True)

    # Browser configuration
    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    # Crawl configuration
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        screenshot=True,
        pdf=True,
        capture_mhtml=True,
    )

    # Launch crawler
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=url,
            config=crawler_config,
        )

    # Return if crawl failed
    if not result.success:
        return {
            "success": False,
            "method": "snapshot",
            "url": url,
            "message": "Crawl failed",
        }

    screenshot_path = None
    pdf_path = None
    mhtml_path = None

    # Save Screenshot
    if result.screenshot:
        screenshot_path = "outputs/screenshot.png"
        with open(screenshot_path, "wb") as file:
            file.write(base64.b64decode(result.screenshot))

    # Save PDF
    if result.pdf:
        pdf_path = "outputs/page.pdf"
        with open(pdf_path, "wb") as file:
            file.write(result.pdf)

    # Save MHTML
    if result.mhtml:
        mhtml_path = "outputs/page.mhtml"
        with open(mhtml_path, "w", encoding="utf-8") as file:
            file.write(result.mhtml)

    # Return response
    return {
        "success": True,
        "method": "snapshot",
        "url": url,
        "screenshot": screenshot_path,
        "pdf": pdf_path,
        "mhtml": mhtml_path,
    }
