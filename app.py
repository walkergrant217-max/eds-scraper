import streamlit as st
import openai
import requests
import pandas as pd
from duckduckgo_search import DDGS

# === CONFIGURE ===
openai.api_key = "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"
PASSWORD = "vJ2fPq94tZLs"

# === PASSWORD PROTECTION ===
def check_password():
    def password_entered():
        if st.session_state["password"] == PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        st.error("😕 Incorrect password")
        return False
    else:
        return True

# === SEARCH + EXTRACTION ===
def search_duckduckgo(industry, niche, num_results=15):
    query = f"{industry} {niche} companies directory"
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=num_results)
    return results

def extract_company_data(result_text):
    prompt = f"""
Extract company contact info from the following search result. Provide only real companies. Output as JSON with the fields: company_name, website, email, phone, address, social_media (if available), estimated_employees, estimated_revenue.

Text:
{result_text}

Return ONLY valid company info.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        content = response.choices[0].message.content
        return content
    except Exception as e:
        return f"Error: {e}"

def parse_json_response(response):
    try:
        json_obj = eval(response) if isinstance(response, str) else response
        return pd.DataFrame(json_obj if isinstance(json_obj, list) else [json_obj])
    except:
        return pd.DataFrame()

# === MAIN ===
def main():
    if not check_password():
        return

    st.title("🔍 Express Database Solutions – AI Company Scraper")
    st.markdown("Enter your industry and niche to get real, verified company data.")

    industry = st.text_input("Industry", placeholder="e.g., Veterinary")
    niche = st.text_input("Niche", placeholder="e.g., diagnostic labs or software providers")

    if st.button("Find Companies"):
        if not industry or not niche:
            st.warning("Please fill in both fields.")
            return

        with st.spinner("Searching..."):
            results = search_duckduckgo(industry, niche, num_results=15)

        st.success(f"Found {len(results)} search results. Extracting company info...")

        df_final = pd.DataFrame()
        for r in results:
            raw = extract_company_data(r.get("body", ""))
            df_piece = parse_json_response(raw)
            df_final = pd.concat([df_final, df_piece], ignore_index=True)

        if not df_final.empty:
            df_final.drop_duplicates(subset=["company_name", "website"], inplace=True)
            st.dataframe(df_final)
            st.download_button("📥 Download CSV", data=df_final.to_csv(index=False), file_name="company_data.csv", mime="text/csv")
        else:
            st.error("No valid companies found.")

if __name__ == "__main__":
    main()
