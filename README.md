# 🕷️ Crawl4AI Web Scraper

A professional web scraping application built using **Crawl4AI**, **FastAPI**, and **Streamlit**.

## 🚀 Features
- Single Page Crawling
- Deep Crawling (BFS)
- CSS Extraction
- XPath Extraction
- Regex Extraction
- PDF Extraction
- FastAPI Backend
- Streamlit Frontend
- JSON Output
## 🛠️ Tech Stack
- Python 3.13
- Crawl4AI
- Playwright
- FastAPI
- Streamlit
- Requests
## 📁 Project Structure

```
task1/
│
├── backend/
│   ├── crawlers/
│   ├── main.py
│   └── models.py
│
├── frontend/
│   └── app.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/<your-username>/crawl4ai-web-scraper.git
cd crawl4ai-web-scraper
```

### Create Virtual Environment

```bash
python -m venv .venv
```
### Activate
Windows
```bash
.venv\Scripts\activate
```
Linux/macOS
```bash
source .venv/bin/activate
```
### Install Requirements

```bash
pip install -r requirements.txt
```
### Install Playwright Browser
```bash
playwright install
```
## ▶️ Run FastAPI
```bash
cd backend
uvicorn main:app
```
## ▶️ Run Streamlit
```bash
cd frontend
streamlit run app.py
## 📄 License
MIT License