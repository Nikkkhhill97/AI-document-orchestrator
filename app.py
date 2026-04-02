import streamlit as st
import pdfplumber
import json
import requests
from groq import Groq

# --- SETUP GROQ ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Document Orchestrator", page_icon="📄", layout="wide")
st.title("📄 AI-Powered Document Orchestrator")
st.markdown("Upload a document, ask a question, and let AI do the work!")

# --- STEP 1: FILE UPLOAD ---
st.header("Step 1: Upload Your Document")
uploaded_file = st.file_uploader("Choose a PDF or TXT file", type=["pdf", "txt"])

extracted_text = ""

if uploaded_file is not None:
    if uploaded_file.type == "application/pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                extracted_text += page.extract_text() or ""
        st.success("✅ PDF uploaded and text extracted!")
    elif uploaded_file.type == "text/plain":
        extracted_text = uploaded_file.read().decode("utf-8")
        st.success("✅ Text file uploaded!")

    st.subheader("📋 Extracted Text Preview:")
    st.text_area("Raw Text (first 500 chars)", extracted_text[:500], height=200)

# --- STEP 2: QUESTION INPUT ---
st.header("Step 2: Ask a Question About the Document")
user_question = st.text_input("Enter your question", key="user_question")

# --- SESSION STATE ---
if "extracted_json" not in st.session_state:
    st.session_state.extracted_json = None

# --- STEP 3: GROQ EXTRACTION ---
if extracted_text and user_question:
    if st.button("🔍 Analyze Document"):
        with st.spinner("AI is analyzing your document..."):
            prompt = f"""You are a JSON-only response bot. You must respond with ONLY a JSON object, nothing else.

Document content:
{extracted_text}

User question: {user_question}

Respond with ONLY this JSON structure, no other text before or after:
{{
  "key_finding_1": "value",
  "key_finding_2": "value",
  "key_finding_3": "value",
  "key_finding_4": "value",
  "key_finding_5": "value",
  "risk_level": "High or Medium or Low"
}}

Rules:
- Replace key_finding_1 through 5 with actual relevant field names from the document
- Extract values that answer the user question
- risk_level must be exactly "High", "Medium", or "Low"
- DO NOT write anything before or after the JSON
- DO NOT use markdown or code blocks
- ONLY output the raw JSON object starting with {{ and ending with }}"""

            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a JSON-only bot. You never write anything except valid JSON objects. No explanations, no markdown, no code blocks. Only raw JSON."},
                        {"role": "user", "content": prompt}
                    ]
                )
                raw = response.choices[0].message.content.strip()

                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()

                if not raw:
                    st.error("❌ AI returned empty response. Try again.")
                else:
                    parsed = json.loads(raw)
                    st.session_state.extracted_json = parsed

            except json.JSONDecodeError as e:
                st.error(f"❌ JSON parsing error: {e}")
            except Exception as e:
                st.error(f"❌ Groq error: {e}")

# --- OUTPUT 1: DISPLAY EXTRACTED JSON ---
if st.session_state.extracted_json:
    st.header("📊 Output 1: Structured Data Extracted")
    st.json(st.session_state.extracted_json)
    st.success("✅ Extraction complete! Scroll down to send email alert.")

    # --- STEP 4: EMAIL SECTION ---
    st.header("Step 3: Send Alert Email")
    recipient_email = st.text_input("Enter Recipient Email ID", key="recipient_email")

    if st.button("📧 Send Alert Mail"):
        if not recipient_email:
            st.error("❌ Please enter a recipient email!")
        else:
            with st.spinner("Sending to n8n workflow..."):
                payload = {
                    "text": extracted_text,
                    "extracted_json": st.session_state.extracted_json,
                    "question": user_question,
                    "recipient_email": recipient_email
                }

                try:
                    response = requests.post(
                        st.secrets["N8N_WEBHOOK_URL"],
                        json=payload,
                        timeout=30
                    )
                    result = response.json()

                    st.header("📊 Output 2: Final Analytical Answer")
                    st.write(result.get("final_answer", "No answer received"))

                    st.header("📧 Output 3: Generated Email Body")
                    st.write(result.get("email_body", "No email body received"))

                    st.header("✅ Output 4: Email Automation Status")
                    status = result.get("status", "Unknown")
                    if status == "SENT":
                        st.success(f"🚨 Alert Email Status: {status}")
                    else:
                        st.warning(f"📋 Status: {status}")

                except Exception as e:
                    st.error(f"❌ Webhook error: {e}")