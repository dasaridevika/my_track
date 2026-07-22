from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import CrawlRequest

from crawlers.single_page import crawl_single_page
from crawlers.deepcrawl import deep_crawl
from crawlers.jsonCssExtraction import css_extract
from crawlers.jsonXpathExtraction import xpath_extract
from crawlers.RegexExtraction import regex_extract
from crawlers.pdfExtraction import pdf_extract

app = FastAPI(title="Crawl4AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "API Running 🚀"}


@app.post("/crawl")
async def crawl(request: CrawlRequest):

    if request.method == "single":
        return await crawl_single_page(request.url)

    elif request.method == "deep":
        return await deep_crawl(request.url)

    elif request.method == "css":
        return await css_extract(request.url)

    elif request.method == "xpath":
        return await xpath_extract(request.url)

    elif request.method == "regex":
        return await regex_extract(request.url)

    elif request.method == "pdf":
        return await pdf_extract(request.url)

    raise HTTPException(status_code=400, detail="Invalid method")