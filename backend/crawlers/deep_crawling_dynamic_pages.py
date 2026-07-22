import nest_asyncio
from urllib.parse import urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)

from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    DomainFilter,
)

nest_asyncio.apply()


async def deep_crawl_bfs(url: str):

    browser_config = BrowserConfig(
        headless=True,
        verbose=True
    )

    js_code = [
        """
        const btn = Array.from(document.querySelectorAll("button"))
            .find(b => b.innerText.includes("Load More"));

        if (btn) {
            btn.click();
        }
        """
    ]

    domain = urlparse(url).netloc

    url_filter = FilterChain([
        DomainFilter(
            allowed_domains=[domain]
        )
    ])

    bfs_strategy = BFSDeepCrawlStrategy(
        max_depth=1,
        include_external=False,
        filter_chain=url_filter,
    )

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id="deep_bfs_session",
        js_code=js_code,
        deep_crawl_strategy=bfs_strategy,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(
            url=url,
            config=crawler_config,
        )

    if not isinstance(results, list):
        results = [results]

    pages = []

    for page in results:
        pages.append({
            "url": page.url,
            "success": page.success,
            "markdown": (
                page.markdown.fit_markdown[:500]
                if page.success and page.markdown
                else None
            ),
            "metadata": page.metadata,
        })

    return {
        "success": True,
        "method": "dynamic",
        "total_pages": len(pages),
        "pages": pages,
    }