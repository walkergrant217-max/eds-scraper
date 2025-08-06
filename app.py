import streamlit as st
import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
from duckduckgo_search import ddg  # pip install duckduckgo_search

BASE_URL = "https://opencorporates.com/companies"
HEADERS = {
    "User-Agent": "EDS Scraper - Contact: your_email@example.com"
}
RATE_LIMIT = 2  # seconds between requests


def scrape_opencorporates(industry_keyword, max_pages=3):
    results = []

    for page in range(1, max_pages + 1):
        params = {
            'q': industry_keyword,
            'page': page
        }
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            st.warning(f"Failed to get page {page} from OpenCorporates")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        company_rows = soup.select('table.companies tr.company')

        if not company_rows:
            st.info("No more results found.")
            break

        for row in company_rows:
            name_cell = row.select_one('td.name a')
            jurisdiction_cell = row.select_one('td.jurisdiction')
            company_number_cell = row.select_one('td.company_number')

            if not name_cell or not jurisdiction_cell or not company_number_cell:
                continue

            company_name = name_cell.text.strip()
            company_url = "https://opencorporates.com" + name_cell['href']
            jurisdiction = jurisdiction_cell.text.strip()
            company_number = company_number_cell.text.strip()

            results.append({
                "Name": company_name,
                "Jurisdiction": jurisdiction,
                "Company Number": company_number,
                "Profile URL": company_url
            })

        time.sleep(RATE_LIMIT)

    return pd.DataFrame(results)


def valid_website_url(url, company_name):
    forbidden_domains = ['facebook.com', 'linkedin.com', 'twitter.com', 'youtube.com', 'wikipedia.org', 'opencorporates.com']
    url_lower = url.lower()
    if any(domain in url_lower for domain in forbidden_domains):
        return False

    company_words = [w.lower() for w in company_name.split() if len(w) > 3]
    matches = sum(1 for w in company_words if w in url_lower)
    return matches >= 1


def find_website_duckduckgo(company_name, jurisdiction):
    query = f"{company_name} {jurisdiction} official website"
    try:
        results = ddg(query, max_results=3)
        if results:
            for result in results:
                url = result.get('href') or result.get('url')
                if url and valid_website_url(url, company_name):
                    return url
    except Exception as e:
        st.warning(f"DuckDuckGo search error: {e}")
    return None


def enrich_with_websites(df):
    websites = []
    progress_bar = st.progress(0)
    total = len(df)
    for idx, row in df.iterrows():
        website = find_website_duckduckgo(row['Name'], row['Jurisdiction'])
        websites.append(website)
        progress_bar.progress((idx + 1) / total)
        time.sleep(1)
    df['Website'] = websites
    return df


def main():
    st.title("Express Database Solutions (EDS) - Company Finder")

    industry = st.text_input("Enter industry keyword(s) to search for companies", value="orthopedic hospitals")
    max_pages = st.slider("Number of OpenCorporates result pages to scrape (about 10-20 companies per page)", 1, 5, 3)

    if st.button("Start Scraping"):
        with st.spinner("Scraping OpenCorporates..."):
            df_companies = scrape_opencorporates(industry, max_pages=max_pages)
            st.success(f"Scraped {len(df_companies)} companies from OpenCorporates.")

        with st.spinner("Searching DuckDuckGo for company websites... (this may take a while)"):
            df_enriched = enrich_with_websites(df_companies)

        st.success("Company data enriched with websites.")
        st.dataframe(df_enriched)

        to_download = df_enriched.fillna("").to_excel(index=False)
        st.download_button(
            label="📥 Download results as Excel",
            data=to_download,
            file_name=f"eds_companies_{industry.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


if __name__ == "__main__":
    main()
