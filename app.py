import streamlit as st
import openai
import pandas as pd
import re
import validators
from duckduckgo_search import ddg

# Hardcoded password
APP_PASSWORD = "vJ2fPq94t2Ls"

# Your OpenAI API key should be set as environment variable OPENAI_API_KEY for security
openai.api_key = st.secrets.get("OPENAI_API_KEY") or ""

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def validate_url(url):
    return validators.url(url)

def extract_contact_info(text):
    phone_pattern = r'(\+?\d{1,2}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}'
    email_pattern = r'[\w\.-]+@[\w\.-]+'
    phones = re.findall(phone_pattern, text)
    emails = re.findall(email_pattern, text)
    phone = phones[0][0] if phones else ""
    email = emails[0] if emails else ""
    return phone, email

def generate_prompt(industry, additional_categories, company_text):
    categories_str = ", ".join(["Company Name", "URL", "Address", "Phone", "Email"] + additional_categories)
    prompt = (
        f"From the following company description, extract the following details as JSON: {categories_str}. "
        f"Return empty string \"\" for any missing data.\n\nCompany info:\n{company_text}\n\nJSON:"
    )
    return prompt

def query_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return None

def parse_openai_response(response):
    try:
        # Sometimes response has formatting issues, try to fix it:
        json_str = response.strip()
        # Convert single quotes to double quotes if necessary:
        json_str = json_str.replace("'", '"')
        data = pd.io.json.loads(json_str)
        return data
    except Exception:
        # If JSON parsing fails, return raw text for manual check
        return None

def search_companies(industry, max_results=250):
    query = f"{industry} companies USA"
    results = ddg(query, max_results=max_results)
    if not results:
        return []
    return results

def main():
    st.title("Express Database Solutions (EDS) Vendor Scraper")

    password = st.text_input("Enter password to access:", type="password")
    if password != APP_PASSWORD:
        st.warning("Incorrect password. Please try again.")
        st.stop()

    industry = st.text_input("Enter industry (e.g. 'Veterinary Hospitals')", value="")
    additional_input = st.text_input(
        "Enter additional categories requested (comma separated, e.g. LinkedIn Handle, Employee Number)", value=""
    )
    additional_categories = [x.strip() for x in additional_input.split(",") if x.strip()]
    max_entries = st.number_input("Number of entries to return", min_value=1, max_value=2000, value=250, step=1)
    location = st.text_input("Optional: Specify location (e.g. United States)", value="United States")

    if st.button("Start scraping"):
        if not industry:
            st.error("Please enter an industry.")
            return

        with st.spinner("Searching companies..."):
            raw_results = search_companies(industry, max_results=max_entries * 2)  # extra to allow filtering duplicates
            st.success(f"Found {len(raw_results)} raw results")

        companies = []
        urls_seen = set()

        for item in raw_results:
            if len(companies) >= max_entries:
                break

            url = item.get('href') or item.get('url') or ""
            if not validate_url(url) or url in urls_seen:
                continue

            title = item.get('title') or ""
            snippet = item.get('body') or item.get('snippet') or ""

            combined_text = f"{title}\n{snippet}\nURL: {url}"

            prompt = generate_prompt(industry, additional_categories, combined_text)
            response = query_openai(prompt)
            if not response:
                continue

            try:
                company_data = pd.io.json.loads(response.replace("'", '"'))
            except Exception:
                company_data = None

            if company_data and isinstance(company_data, dict):
                # Deduplicate by company URL
                company_url = company_data.get("URL", "")
                if company_url and company_url not in urls_seen:
                    urls_seen.add(company_url)
                    companies.append(company_data)

        if not companies:
            st.warning("No companies could be extracted. Try broadening your search or check API usage.")
            return

        df = pd.DataFrame(companies)

        # Highlight unverified or missing data cells in yellow
        def highlight_missing(s):
            return ['background-color: yellow' if (v == "" or pd.isna(v)) else '' for v in s]

        st.dataframe(df.style.apply(highlight_missing, axis=1))

        # Export to Excel
        towrite = pd.ExcelWriter("eds_scraped_companies.xlsx", engine='openpyxl')
        df.to_excel(towrite, index=False)
        towrite.save()

        with open("eds_scraped_companies.xlsx", "rb") as f:
            st.download_button("📥 Download as Excel", data=f, file_name="eds_scraped_companies.xlsx")

if __name__ == "__main__":
    main()
