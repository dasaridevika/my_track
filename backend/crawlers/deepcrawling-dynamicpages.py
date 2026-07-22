import asyncio
import nest_asyncio

nest_asyncio.apply()

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


async def deep_crawl_bfs():

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

    url_filter = FilterChain([
        DomainFilter(
            allowed_domains=["quotes.toscrape.com"]
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

    async with AsyncWebCrawler(
        config=browser_config
    ) as crawler:

        results = await crawler.arun(
            url="https://www.geeksforgeeks.org/",
            config=crawler_config,
        )

        print("=" * 60)
        print(f"Total Pages Crawled : {len(results)}")
        print("=" * 60)
        for i, page in enumerate(results, start=1):
            print(f"\nPage {i}")
            print(f"URL      : {page.url}")
            print(f"Success  : {page.success}")
            if page.success and page.markdown:
                print(page.markdown.fit_markdown[:500])
asyncio.run(deep_crawl_bfs())