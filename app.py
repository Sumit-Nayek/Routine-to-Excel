# import os
# import json
# import base64
# from io import BytesIO
# import streamlit as st
# import pandas as pd
# from pypdf import PdfReader
# import requests

# # Page setup
# st.set_page_config(page_title="Routine to Excel", page_icon="📅", layout="centered")
# st.title("📅 Student Routine to Excel Converter")
# st.write("Upload your exam/class schedule (PDF or Image) to convert it into a structured Excel file.")

# # 1. Retrieve API key securely from environment variable
# API_KEY = os.getenv("NVIDIA_API_KEY")

# if not API_KEY:
#     st.error("API Key not detected in environment variables. Please check your setup.")
#     st.stop()

# # 2. Helper function: Extract text from PDF
# def extract_text_from_pdf(uploaded_file):
#     reader = PdfReader(uploaded_file)
#     extracted_text = ""
#     for page in reader.pages:
#         text = page.extract_text()
#         if text:
#             extracted_text += text + "\n"
#     return extracted_text

# # 3. Helper function: Call NVIDIA NIM API
# def parse_schedule_with_llm(content_text=None, base64_image=None):
#     url = "https://integrate.api.nvidia.com/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "Content-Type": "application/json"
#     }

#     system_prompt = (
#         "You are an expert timetable parsing assistant. "
#         "Extract all scheduled classes/exams into a clean list. "
#         "You must respond ONLY with a valid JSON array of objects. "
#         "Each object must contain these exact keys: 'Date', 'Day', 'Time', 'Subject', 'Room'. "
#         "If an attribute is not found, set its value to 'N/A'. Do not include markdown formatting or extra text."
#     )

#     if base64_image:
#         # Use Vision Model for images
#         model_name = "meta/llama-3.2-11b-vision-instruct"
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": "Extract the schedule details from this routine image into the required JSON format."},
#                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
#                 ]
#             }
#         ]
#     else:
#         # Use Text Model for extracted PDF text
#         model_name = "meta/llama-3.1-8b-instruct"
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": f"Extract schedule details from this text:\n\n{content_text}"}
#         ]

#     payload = {
#         "model": model_name,
#         "messages": messages,
#         "temperature": 0.1,
#         "max_tokens": 2048
#     }

#     response = requests.post(url, headers=headers, json=payload)
    
#     if response.status_code != 200:
#         raise Exception(f"API Error ({response.status_code}): {response.text}")
        
#     raw_content = response.json()["choices"][0]["message"]["content"].strip()
    
#     # Strip accidental markdown wrapping if present
#     if raw_content.startswith("```"):
#         raw_content = raw_content.strip("`").replace("json", "").strip()
        
#     return json.loads(raw_content)

# # 4. File Uploader UI
# uploaded_file = st.file_uploader("Upload Routine (PDF, PNG, JPG, JPEG)", type=["pdf", "png", "jpg", "jpeg"])

# if uploaded_file and st.button("Convert to Excel"):
#     with st.spinner("Analyzing schedule and generating table..."):
#         try:
#             # Process based on file type
#             if uploaded_file.type == "application/pdf":
#                 extracted_text = extract_text_from_pdf(uploaded_file)
#                 if not extracted_text.strip():
#                     st.error("Could not extract readable text from this PDF. If it's a scanned PDF, convert it to an image first.")
#                     st.stop()
#                 data = parse_schedule_with_llm(content_text=extracted_text)
#             else:
#                 image_bytes = uploaded_file.read()
#                 base64_img = base64.b64encode(image_bytes).decode("utf-8")
#                 data = parse_schedule_with_llm(base64_image=base64_img)

#             # Convert to Pandas DataFrame
#             df = pd.DataFrame(data)
            
#             st.success("Routine parsed successfully!")
#             st.dataframe(df, use_container_width=True)

#             # Generate Excel in memory
#             excel_buffer = BytesIO()
#             with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
#                 df.to_excel(writer, index=False, sheet_name="Routine")
#             excel_data = excel_buffer.getvalue()

#             # Download Button
#             st.download_button(
#                 label="📥 Download Excel File",
#                 data=excel_data,
#                 file_name="student_routine.xlsx",
#                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )

#         except Exception as e:
#             st.error(f"Error parsing file: {e}")
import os
import json
from io import BytesIO
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from huggingface_hub import InferenceClient

# Page setup
st.set_page_config(page_title="Routine to Excel", page_icon="📅", layout="centered")
st.title("📅 Student Routine to Excel Converter")
st.write("Upload your exam/class schedule (PDF) to convert it into a structured Excel file.")

# 1. Retrieve Hugging Face Token securely
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    st.error("HF_TOKEN not detected in environment variables. Please run: export HF_TOKEN='your_token'")
    st.stop()

# Initialize the HF Inference Client
client = InferenceClient(api_key=HF_TOKEN)

# 2. Helper function: Extract text from PDF
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    extracted_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"
    return extracted_text

# 3. Helper function: Call Hugging Face API
def parse_schedule_with_hf(content_text):
    system_prompt = (
        "You are an expert data parser. Extract the timetable/schedule information into a structured table. "
        "Return ONLY a valid JSON array of objects. "
        "Each object must contain these exact keys: 'Date', 'Day', 'Time', 'Subject', 'Room'. "
        "If a field is missing, set its value to 'N/A'. "
        "Do not include any Markdown ticks (no ```json or ```) or conversational text. Output raw JSON only."
    )

    # Use a widely supported free serverless instruct model
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract schedule details from this text:\n\n{content_text}"}
        ],
        max_tokens=2048,
        temperature=0.1
    )

    raw_content = response.choices[0].message.content.strip()

    # Clean any leftover markdown blocks
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`").replace("json", "").strip()

    return json.loads(raw_content)

# 4. Streamlit UI
uploaded_file = st.file_uploader("Upload Routine (PDF)", type=["pdf"])

if uploaded_file and st.button("Convert to Excel"):
    with st.spinner("Analyzing schedule and generating table..."):
        try:
            extracted_text = extract_text_from_pdf(uploaded_file)
            
            if not extracted_text.strip():
                st.error("No readable text found in this PDF. Please ensure it is a digital (selectable text) PDF.")
                st.stop()

            # Parse with Hugging Face
            data = parse_schedule_with_hf(extracted_text)

            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            st.success("Routine parsed successfully!")
            st.dataframe(df, use_container_width=True)

            # Generate Excel file
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Routine")
            excel_data = excel_buffer.getvalue()

            # Download Button
            st.download_button(
                label="📥 Download Excel File",
                data=excel_data,
                file_name="student_routine.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error parsing file: {e}")