from pydantic import BaseModel
class CrawlRequest(BaseModel):
    url: str
    method: str