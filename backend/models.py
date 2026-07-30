from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CrawlRequest(BaseModel):
    url: str = Field(..., description="Target HTTP or HTTPS URL")
    method: str = Field("single", description="Crawl method: single, deep, dynamic, snapshot, css, xpath, regex, pdf")
    categories: Optional[List[str]] = Field(default=None, description="Category or keyword list for Best-First Deep Crawling")
    max_depth: Optional[int] = Field(default=1, description="Maximum crawl depth (1-2 recommended for free tier)")
    max_pages: Optional[int] = Field(default=5, description="Maximum total pages to crawl (1-10 recommended for free tier)")
    css_schema: Optional[Dict[str, Any]] = Field(default=None, description="Custom CSS extraction schema")
    xpath_schema: Optional[Dict[str, Any]] = Field(default=None, description="Custom XPath extraction schema")
    regex_patterns: Optional[Dict[str, str]] = Field(default=None, description="Custom Regex patterns")