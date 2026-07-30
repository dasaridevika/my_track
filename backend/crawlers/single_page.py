import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

run_config = CrawlerRunConfig()
browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,
    ignore_https_errors=True,
    headers={"Accept-Language": "en-US,en;q=0.9"},
    extra_args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--js-flags=--max-old-space-size=128",
        "--lang=en-US"
    ]
)



def extract_clean_links(raw_links) -> dict:
    if not raw_links:
        return {"internal": [], "external": [], "total_count": 0}
    clean_internal = []
    clean_external = []
    seen = set()

    if isinstance(raw_links, dict):
        internal_list = raw_links.get("internal", []) or []
        external_list = raw_links.get("external", []) or []
        for item in internal_list:
            href = item.get("href", "") if isinstance(item, dict) else str(item or "")
            text = item.get("text", "") if isinstance(item, dict) else href
            if href and href not in seen:
                seen.add(href)
                clean_internal.append({"href": href, "text": text or href, "type": "internal"})
        for item in external_list:
            href = item.get("href", "") if isinstance(item, dict) else str(item or "")
            text = item.get("text", "") if isinstance(item, dict) else href
            if href and href not in seen:
                seen.add(href)
                clean_external.append({"href": href, "text": text or href, "type": "external"})
    elif isinstance(raw_links, list):
        for item in raw_links:
            href = item.get("href", "") if isinstance(item, dict) else str(item or "")
            text = item.get("text", "") if isinstance(item, dict) else href
            if href and href not in seen:
                seen.add(href)
                clean_internal.append({"href": href, "text": text or href, "type": "internal"})

    return {
        "internal": clean_internal,
        "external": clean_external,
        "total_count": len(clean_internal) + len(clean_external),
    }


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

        cleaned_links = extract_clean_links(getattr(result, "links", {}))

        return {
            "success": getattr(result, "success", False),
            "url": url,
            "markdown": str(md or ""),
            "html": getattr(result, "html", ""),
            "links": cleaned_links,
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
