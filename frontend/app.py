import streamlit as st
import requests

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Crawl4AI Web Scraper",
    page_icon="🕷️",
    layout="wide"
)

# -----------------------------
# Backend API URL
# -----------------------------
API_URL = "mytrack-production-c89f.up.railway.app/crawl"

# -----------------------------
# UI
# -----------------------------
st.title("🕷️ Crawl4AI Web Scraper")
st.write("Extract structured information from websites using Crawl4AI.")

url = st.text_input("🌐 Enter Website URL")

method = st.selectbox(
    "📌 Select Extraction Method",
    [
        "single",
        "deep",
        "dynamic",
        "snapshot",
        "css",
        "xpath",
        "regex",
        "pdf"
    ]
)

# -----------------------------
# Crawl Button
# -----------------------------
if st.button("🚀 Start Crawling", use_container_width=True):

    if not url.strip():
        st.warning("Please enter a URL.")

    else:
        payload = {
            "url": url,
            "method": method
        }

        try:
            with st.spinner("🕷️ Crawling website... Please wait..."):

                response = requests.post(
                    API_URL,
                    json=payload,
                    timeout=300
                )

            if response.status_code == 200:

                st.success("✅ Crawling Completed!")

                res_data = response.json()

                # Some APIs wrap the response inside "data"
                data = res_data.get("data", res_data)

                # ===========================================
                # Deep Crawl / Dynamic Crawl
                # ===========================================
                if method in ["deep", "dynamic"]:

                    st.subheader("🌐 Crawl Results")

                    pages = data.get("pages", [])

                    if pages:

                        st.write(
                            f"**Total Pages Crawled:** {data.get('total_pages', len(pages))}"
                        )

                        for i, page in enumerate(pages, start=1):

                            st.markdown(f"### 📄 Page {i}")

                            st.write(f"**URL:** {page.get('url')}")
                            st.write(f"**Success:** {page.get('success')}")

                            if page.get("metadata"):
                                with st.expander("Metadata"):
                                    st.json(page["metadata"])

                            if page.get("markdown"):
                                with st.expander("Markdown Preview"):
                                    st.markdown(page["markdown"])

                            st.divider()

                    else:
                        st.warning("No pages were returned.")

                # ===========================================
                # Snapshot
                # ===========================================
                elif method == "snapshot":

                    st.subheader("📸 Page Snapshot")

                    st.write(f"**URL:** {data.get('url')}")
                    st.write(f"**Success:** {data.get('success')}")

                    if data.get("screenshot"):
                        st.success(f"Screenshot saved at: {data['screenshot']}")

                    if data.get("pdf"):
                        st.success(f"PDF saved at: {data['pdf']}")

                    if data.get("mhtml"):
                        st.success(f"MHTML saved at: {data['mhtml']}")

                    with st.expander("Snapshot Response"):
                        st.json(data)

                # ===========================================
                # PDF Extraction
                # ===========================================
                elif method == "pdf":

                    st.subheader("📄 PDF Extraction")

                    st.json(data)

                # ===========================================
                # CSS / XPath / Regex / Single
                # ===========================================
                else:

                    st.subheader("📄 Extraction Result")

                    st.json(data)

            else:

                st.error(f"❌ API Error: {response.status_code}")

                try:
                    st.json(response.json())
                except Exception:
                    st.text(response.text)

        except requests.exceptions.Timeout:

            st.error(
                "⏳ Request timed out. The backend may still be processing. Please try again."
            )

        except requests.exceptions.ConnectionError:

            st.error(
                "❌ Unable to connect to the backend API. Please ensure the backend is running."
            )

        except Exception as e:

            st.error(f"Unexpected Error: {e}")
