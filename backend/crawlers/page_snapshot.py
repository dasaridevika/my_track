import asyncio
import os
import base64
from crawl4ai import(AsyncWebCrawler,BrowserConfig,CrawlerRunConfig,CacheMode,)
async def page_snapshot():
    #Create output directory
    os.makedirs("outputs",exist_ok=True)
    browser_config=BrowserConfig(
    headless=True,
    verbose=True,)
    #Crawl COnfiguration
    crawler_config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS,screenshot=True,pdf=True,capture_mhtml=True,)
    #Launch Crawler
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result=await crawler.arun(url="https://www.geeksforgeeks.org/",config=crawler_config)
        if not result.success:
            print("Crawl Failed")
        #Save Screenshot
        if result.screenshot:
            with open("outputs/screenshot.png", "wb") as file:
                file.write(base64.b64decode(result.screenshot))
            print("Screenshot saved")
        #Save PDF
        if result.pdf:
            with open("outputs/page.pdf","wb") as file:
                file.write(result.pdf)
            print("PDF saved")
        #Save MTHML
        if result.mhtml:
            with open("outputs/page.mhtml","w",encoding="utf-8") as file:
                file.write(result.mhtml)
            print("MHTML saved")
        if not result.success:
            print("Crawl Failed")
            return
asyncio.run(page_snapshot())
        