import uuid
import asyncio
import logging
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

logger = logging.getLogger(__name__)


def get_markdown_text(markdown) -> str:
    if not markdown:
        return ""
    if isinstance(markdown, str):
        return markdown
    return (
        getattr(markdown, "fit_markdown", None)
        or getattr(markdown, "raw_markdown", None)
        or str(markdown or "")
    )


async def deep_crawl_bfs(
    url: str,
    categories: Optional[List[str]] = None,
    max_depth: int = 1,
    max_pages: int = 5,
    **kwargs
):
    """Deep crawl dynamic pages using Best-First strategy when categories/keywords are provided,

    or BFS strategy when no categories are specified. Supports JavaScript button clicks (e.g. Load More).
    """
    session_id = f"dynamic_{uuid.uuid4().hex[:8]}"
    
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        enable_stealth=True,
        ignore_https_errors=True,
        extra_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage"
        ]
    )

    js_code = [
        """
        try {
            const btn = Array.from(document.querySelectorAll("button, a"))
                .find(b => {
                    const text = (b.innerText || b.textContent || "").toLowerCase();
                    return text.includes("load more") || text.includes("show more") || text.includes("view more");
                });

            if (btn) {
                btn.click();
            }
        } catch (e) {
            console.log("No dynamic button clicked:", e);
        }
        """
    ]

    domain = urlparse(url).netloc
    url_filter = FilterChain([
        DomainFilter(allowed_domains=[domain])
    ])

    # Clean and filter categories
    cleaned_categories = [cat.strip() for cat in (categories or []) if cat and str(cat).strip()]

    if cleaned_categories:
        logger.info(f"Dynamic crawl using BestFirst strategy with categories: {cleaned_categories}")
        scorer = KeywordRelevanceScorer(keywords=cleaned_categories, weight=1.0)
        crawl_strategy = BestFirstCrawlingStrategy(
            max_depth=min(max_depth, 2),
            max_pages=min(max_pages, 10),
            include_external=False,
            filter_chain=url_filter,
            url_scorer=scorer,
        )
    else:
        logger.info("Dynamic crawl using standard BFS strategy")
        crawl_strategy = BFSDeepCrawlStrategy(
            max_depth=min(max_depth, 2),
            max_pages=min(max_pages, 10),
            include_external=False,
            filter_chain=url_filter,
        )

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=session_id,
        js_code=js_code,
        deep_crawl_strategy=crawl_strategy,
        semaphore_count=1,
        page_timeout=35000,
    )

    try:
        async with asyncio.timeout(90):
            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = await crawler.arun(
                    url=url,
                    config=crawler_config,
                )

        if not isinstance(results, list):
            results = [results]

        pages = []
        for page in results:
            url_val = getattr(page, "url", url)
            success_val = getattr(page, "success", False)
            md_raw = get_markdown_text(getattr(page, "markdown", None))
            
            pages.append({
                "url": url_val,
                "title": getattr(page, "title", "") or "Dynamic Page",
                "success": success_val,
                "markdown": md_raw,
                "content": md_raw,
                "metadata": getattr(page, "metadata", {}),
            })

        return {
            "success": True,
            "method": "dynamic",
            "categories": cleaned_categories,
            "total_pages": len(pages),
            "successful_pages": sum(1 for p in pages if p["success"]),
            "pages": pages,
        }

    except asyncio.TimeoutError:
        logger.error(f"Dynamic crawl timed out for {url}")
        return {
            "success": False,
            "method": "dynamic",
            "error": "Dynamic page crawl timed out after 90 seconds.",
            "pages": []
        }
    except Exception as e:
        logger.exception(f"Dynamic crawl failed for {url}")
        return {
            "success": False,
            "method": "dynamic",
            "error": str(e),
            "pages": []
        }

if __name__ == "__main__":
    async def main():
        data = await deep_crawl_bfs("https://www.geeksforgeeks.org", categories=["python", "tutorial"])
        print(data)

    asyncio.run(main())

