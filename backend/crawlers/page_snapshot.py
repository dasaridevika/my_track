import os
import base64
import uuid

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)

from storage import is_bucket_configured, upload_file, get_download_url

async def page_snapshot(url: str):
    job_id = str(uuid.uuid4())
    output_dir = os.path.join("outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        screenshot=True,
        pdf=True,
        capture_mhtml=True,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawler_config)

    if not result.success:
        return {
            "success": False,
            "method": "snapshot",
            "url": url,
            "message": "Crawl failed",
        }

    uploaded_files = {}

    if result.screenshot:
        screenshot_path = os.path.join(output_dir, "screenshot.png")
        with open(screenshot_path, "wb") as file:
            file.write(base64.b64decode(result.screenshot))

        if is_bucket_configured():
            key = f"pagesnapshots/{job_id}/screenshot.png"
            upload_file(screenshot_path, key)
            uploaded_files["screenshot"] = {
                "key": key,
                "url": get_download_url(key),
            }
        else:
            uploaded_files["screenshot"] = {"local_path": screenshot_path}

    if result.pdf:
        pdf_path = os.path.join(output_dir, "page.pdf")
        with open(pdf_path, "wb") as file:
            file.write(result.pdf)

        if is_bucket_configured():
            key = f"pagesnapshots/{job_id}/page.pdf"
            upload_file(pdf_path, key)
            uploaded_files["pdf"] = {
                "key": key,
                "url": get_download_url(key),
            }
        else:
            uploaded_files["pdf"] = {"local_path": pdf_path}

    if result.mhtml:
        mhtml_path = os.path.join(output_dir, "page.mhtml")
        with open(mhtml_path, "w", encoding="utf-8") as file:
            file.write(result.mhtml)

        if is_bucket_configured():
            key = f"pagesnapshots/{job_id}/page.mhtml"
            upload_file(mhtml_path, key)
            uploaded_files["mhtml"] = {
                "key": key,
                "url": get_download_url(key),
            }
        else:
            uploaded_files["mhtml"] = {"local_path": mhtml_path}

    return {
        "success": True,
        "method": "snapshot",
        "url": url,
        "job_id": job_id,
        "files": uploaded_files,
    }
