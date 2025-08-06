import streamlit as st
import pandas as pd
import re
import phonenumbers
import validators
import tldextract
from ddgs import DDGS
from bs4 import BeautifulSoup
import requests
from email_validator import validate_email, EmailNotValidError

# ----------- Scraping & Extraction Utilities -----------

def extract_emails(text):
    raw_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    valid_emails = []
    for email in raw_emails:
        try:
            valid = validate_email(email)
            valid_emails.append(valid.email)
        except EmailNotValidError:
            continue
    return list(set(valid_emails))

def extract_phone_numbers(text):
    phone_numbers = []
    for match in phonenumbers.PhoneNumberMatcher(text, "US"):
        number = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        if number not in phone_numbers:
            phone_numbers.append(number)
    return phone_numbers

def extract_socials(text):
    socials = {}
    patterns = {
        'LinkedIn': r'https?://(www\.)?linkedin\.com/[^\'" >]+',
        'Facebook': r'https?://(www\.)?facebook\.com/[^\'" >]+',
        'Instagram': r'https?://(www\.)?instagram\.com/[^\'" >]+',
        'Twitter': r'https?://(www\.)?twitter\.com/[^\'" >]+',
        'TikTok': r'https?://(www\.)?tiktok\.com/[^\'" >]+',
    }
    for platform, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            socials[platform] = match.group()
    return socials

def get_website_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return "", [], [], {}
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = extract_emails(text)
        phones = extract_phone_numbers(text)
        socials = extract_socials(resp.text)
        return soup.title.string if soup.title else "", emails, phones, socials
    except:
        return "", [], [], {}

# ----------- DuckDuckGo Search Function -----------

def search_businesses(query, max_results=50):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title"),
                "url": r.get("href"),
                "snippet": r.get("body")
            })
    return results

# ----------- Streamlit UI -----------

st.set_page_config(page_title="EDS Scraper", layout="wide")
st.title("📊 Express Database Solutions: Business Scraper")

industry = st.text_input("Enter target industry (e.g. veterinary, landscaping):")
location = st.text_input("Enter geographic location (e.g. Ohio, US, North Carolina):")
keywords = st.text_input("Optional keywords (e.g. equipment supplier, mobile):")

max_results = st.slider("Number of businesses to scrape", 10, 100, 30)

if st.button("Scrape Businesses"):
    if not industry or not location:
        st.warning("Please enter both industry and location.")
    else:
        query = f"{industry} businesses in {location} {keywords}"
        st.info(f"Searching: '{query}'...")

        results = search_businesses(query, max_results=max_results)
        data = []

        for result in results:
            url = result['url']
            domain_parts = tldextract.extract(url)
            base_domain = f"{domain_parts.domain}.{domain_parts.suffix}"
            name = result['title'] or domain_parts.domain
            snippet = result['snippet'] or ""

            # Website scraping
            title, emails, phones, socials = get_website_info(url)

            # Simulated/optional fields (replace with API data if needed)
            simulated_fields = {
                "Estimated Revenue": "1M–5M USD",
                "Employee Count": "10–50",
                "Industry Category": industry.title(),
                "Headquarters": location.title(),
                "Tags": keywords,
                "Source": "DuckDuckGo",
            }

            row = {
                "Business Name": name,
                "Website URL": url,
                "Domain": base_domain,
                "Website Title": title,
                "Snippet": snippet,
                "Emails": ", ".join(emails),
                "Phones": ", ".join(phones),
                "LinkedIn": socials.get("LinkedIn", ""),
                "Instagram": socials.get("Instagram", ""),
                "Facebook": socials.get("Facebook", ""),
                "Twitter": socials.get("Twitter", ""),
                "TikTok": socials.get("TikTok", ""),
                **simulated_fields
            }
            data.append(row)

        df = pd.DataFrame(data)

        st.success(f"✅ Found {len(df)} companies.")
        st.dataframe(df)

        # Download
        st.download_button("📥 Download as Excel", df.to_excel(index=False), file_name="scraped_businesses.xlsx")
