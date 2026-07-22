import os
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.processors.pdf import (
    PDFCrawlerStrategy,
    PDFContentScrapingStrategy,
)
async def pdf_extract(url: str):
    # Create folder for extracted images
    os.makedirs("pdf_images", exist_ok=True)
    # Configure PDF scraping
    pdf_scraper = PDFContentScrapingStrategy(
        extract_images=True,
        save_images_locally=True,
        image_save_dir="pdf_images",
        batch_size=2,
    )
    run_config = CrawlerRunConfig(
        scraping_strategy=pdf_scraper
    )
    async with AsyncWebCrawler(
        crawler_strategy=PDFCrawlerStrategy()
    ) as crawler:
        result = await crawler.arun(
            url=url,
            config=run_config
        )
    if not result.success:
        return {
            "success": False,
            "error": result.error_message
        }
    # Handle markdown safely
    markdown = (
        result.markdown.raw_markdown
        if hasattr(result.markdown, "raw_markdown")
        else result.markdown
    )
    return {
        "success": True,
        "url": url,
        "metadata": result.metadata,
        "markdown": markdown,
        "images": result.media.get("images", []),
        "image_count": len(result.media.get("images", []))
    }
# Optional: Run directly for testing
if __name__ == "__main__":
    import asyncio
    import json
    async def main():
        data = await pdf_extract(
            "https://adk.elsevierpure.com/ws/portalfiles/portal/59225442/1_EDS_basics.pdf"
        )
        print(json.dumps(data, indent=4, default=str))
    asyncio.run(main())