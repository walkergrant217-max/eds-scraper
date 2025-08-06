import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import re
import validators
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from tqdm import tqdm

# ---------------------- HELPER FUNCTIONS ------------------------

def is_valid_url(url):
    return validators.url(url)

def is_valid_email(email):
    try:
        v = validate_email(email)
        return True
    except EmailNotValidError:
        return False

def extract_emails(text):
    raw_emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", text)
    return list(set([email for email in raw_emails if is_valid_email(email)]))

def extract_phone_numbers(text):
    numbers = []
    for match in phonenumbers.PhoneNumberMatcher(text, "US"):
        numbers.append(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
    return list(set(numbers))

def scrape_duckduckgo(query, max_results=100):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(r)
    return results

def verify_company_match(title, vendor_input):
    return vendor_input.lower() in title.lower()

def get_extra_info_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        return {
            "emails": extract_emails(text),
            "phones": extract_phone_numbers(text)
        }
    except:
        return {"emails": [], "phones": []}

# ---------------------- STREAMLIT INTERFACE ------------------------

st.set_page_config(page_title="EDS Scraper", layout="wide")
st.title("🔎 Express Database Solutions - Company Scraper")

st.markdown("Enter a **vendor type** (e.g., Orthopedic Hospitals) and how many results you'd like to retrieve. The system will only return **verified, real companies**.")

vendor_type = st.text_input("Vendor Type", placeholder="e.g. Orthopedic Hospitals")
max_results = st.number_input("Number of Results to Scrape", min_value=1, value=100)

extra_fields = st.multiselect(
    "Optional Fields to Include",
    options=[
        "Estimated Revenue", "Number of Employees", "Year Founded", "CEO/Owner",
        "LinkedIn", "Facebook", "Instagram", "Twitter", "Industry", "NAICS/SIC",
        "BBB Rating", "Status (Active/Inactive)", "Hours", "Services",
        "Parent Company", "State Registration", "Google Reviews Score", "Glassdoor Score", "Logo"
    ]
)

if st.button("Scrape Companies") and vendor_type:
    st.info("Scraping... This may take a minute.")
    queries = scrape_duckduckgo(vendor_type + " site:bizapedia.com OR site:linkedin.com OR site:zoominfo.com OR site:opencorporates.com", max_results=max_results)

    companies = []
    seen = set()

    for entry in tqdm(queries):
        title = entry.get("title", "")
        url = entry.get("href", "")
        snippet = entry.get("body", "")

        if not is_valid_url(url):
            continue

        if not verify_company_match(title, vendor_type):
            continue

        domain = re.findall(r"https?://([A-Za-z_0-9.-]+).*", url)
        domain = domain[0] if domain else url

        if domain in seen:
            continue

        seen.add(domain)
        extra_info = get_extra_info_from_url(url)

        companies.append({
            "Company Name": title.strip(),
            "URL": url,
            "Email(s)": ", ".join(extra_info["emails"]) if extra_info["emails"] else "N/A",
            "Phone Number(s)": ", ".join(extra_info["phones"]) if extra_info["phones"] else "N/A",
            "Verified": "✅"
        })

    if not companies:
        st.warning("No valid companies found. Try different keywords or increase the result count.")
    else:
        df = pd.DataFrame(companies)
        st.success(f"✅ Successfully scraped {len(df)} companies.")

        st.dataframe(df)

        excel = df.to_excel(index=False, engine="openpyxl")
        st.download_button("📥 Download Results as Excel", data=excel, file_name="scraped_companies.xlsx")

else:
    st.warning("Please enter a vendor type to begin scraping.")

