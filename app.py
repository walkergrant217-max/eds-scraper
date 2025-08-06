import streamlit as st
import openai
import os
from dotenv import load_dotenv
import pandas as pd
import validators
import phonenumbers

load_dotenv()  # Load .env variables

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APP_PASSWORD = "vJ2fPq94t2Ls"

openai.api_key = OPENAI_API_KEY

def check_password():
    """Simple password protection"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        pwd = st.text_input("Enter app password:", type="password")
        if pwd == APP_PASSWORD:
            st.session_state.password_correct = True
            st.experimental_rerun()
        elif pwd:
            st.error("Incorrect password")
        return False
    else:
        return True

def generate_prompt(industry, additional_categories, num_entries):
    base_fields = ["Company Name", "Website URL", "Address", "Phone Number", "Email"]
    additional_fields = [cat.strip() for cat in additional_categories.split(",") if cat.strip()]
    all_fields = base_fields + additional_fields

    prompt = f"""
You are an expert data extractor. For the industry '{industry}', find {num_entries} unique and real companies in the United States. For each company, provide these fields in JSON format, one company per JSON object:

{all_fields}

- If a field is unavailable, leave it blank.
- Do not include duplicates.
- Validate URLs, emails, and phone numbers when possible.
- Return a JSON array of company objects.

Example format:
[
  {{
    "Company Name": "Example Co",
    "Website URL": "https://example.com",
    "Address": "123 Main St, City, State, Zip",
    "Phone Number": "(123) 456-7890",
    "Email": "contact@example.com",
    "LinkedIn Handle": "exampleco",
    "Estimated Revenue": "$10M"
  }},
  ...
]

Respond ONLY with the JSON array.
"""

    return prompt

def call_openai_api(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=3000
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return None

def parse_json_response(response_text):
    import json
    try:
        data = json.loads(response_text)
        return data
    except Exception as e:
        st.error(f"Error parsing JSON response: {e}")
        return None

def validate_and_highlight(df):
    # Validate URLs, emails, phones; mark invalid or missing with highlight
    def highlight_invalid(s):
        return ['background-color: #ffcccc' if (pd.isna(x) or x=="") else '' for x in s]

    # URL validation
    df['Website URL Valid'] = df['Website URL'].apply(lambda x: validators.url(x) if pd.notna(x) and x else False)
    # Email validation
    df['Email Valid'] = df['Email'].apply(lambda x: validators.email(x) if pd.notna(x) and x else False)
    # Phone validation
    def valid_phone(ph):
        if not ph or pd.isna(ph):
            return False
        try:
            parsed = phonenumbers.parse(ph, "US")
            return phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed)
        except:
            return False
    df['Phone Valid'] = df['Phone Number'].apply(valid_phone)

    # Highlight columns with invalid data
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    styles.loc[~df['Website URL Valid'], 'Website URL'] = 'background-color: #ffcccc'
    styles.loc[~df['Email Valid'], 'Email'] = 'background-color: #ffcccc'
    styles.loc[~df['Phone Valid'], 'Phone Number'] = 'background-color: #ffcccc'

    # Drop validation helper columns before display/download
    df_display = df.drop(columns=['Website URL Valid', 'Email Valid', 'Phone Valid'])

    return df_display.style.apply(lambda x: styles.loc[x.name], axis=1)

def main():
    st.title("Express Database Solutions - Company Scraper")

    if not check_password():
        return

    st.markdown("### Enter Search Parameters")

    industry = st.text_input("Industry (e.g. Veterinary Hospitals)", value="")
    additional_cats = st.text_input("Additional Categories (comma separated, e.g. LinkedIn Handle, Estimated Revenue)", value="")
    num_entries = st.number_input("Number of Companies to Retrieve", min_value=1, max_value=5000, value=250)

    if st.button("Start Scraping"):
        if not industry.strip():
            st.error("Industry cannot be empty.")
            return

        prompt = generate_prompt(industry, additional_cats, num_entries)
        with st.spinner("Contacting AI and gathering data... this may take a minute or two."):
            response_text = call_openai_api(prompt)
            if response_text is None:
                return
            data = parse_json_response(response_text)
            if data is None:
                return

            df = pd.DataFrame(data)
            if df.empty:
                st.warning("No data returned.")
                return

            styled_df = validate_and_highlight(df)
            st.dataframe(styled_df, use_container_width=True)

            # Provide Excel download
            towrite = pd.ExcelWriter("output.xlsx", engine='openpyxl')
            df.to_excel(towrite, index=False)
            towrite.save()
            towrite.close()

            with open("output.xlsx", "rb") as f:
                st.download_button(
                    label="📥 Download data as Excel",
                    data=f,
                    file_name="company_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )


if __name__ == "__main__":
    main()
