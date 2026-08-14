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
from datetime import date
from io import BytesIO
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from huggingface_hub import InferenceClient

st.set_page_config(page_title="Attendance Sheet Generator", page_icon="📝", layout="wide")
st.title("📝 Student Attendance Tracker Generator")
st.write("Upload your routine to generate a blank Excel sheet formatted for attendance tracking (Dates on Rows, Subjects as Columns).")

# 1. Retrieve Hugging Face Token securely
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    st.error("HF_TOKEN not detected in environment variables. Run: export HF_TOKEN='your_token'")
    st.stop()

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

# 3. Helper function: Extract subjects and dates using LLM
import re

def clean_subject_name(raw_name: str) -> str:
    """
    Regex fallback to strip standalone subject codes, course numbers, 
    and bracketed codes from the subject name.
    Example: 'CS101 - Data Structures (CSE)' -> 'Data Structures'
    """
    # Remove bracketed codes like [CS101], (MATH-201), (Lec)
    cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_name)
    
    # Remove alphanumeric course codes at the beginning/end (e.g., "CS101: ", "EC-302 - ")
    cleaned = re.sub(r'^[A-Z]{2,5}[-\s]?\d{2,4}\s*[:\-–]?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*[:\-–]?\s*[A-Z]{2,5}[-\s]?\d{2,4}$', '', cleaned, flags=re.IGNORECASE)
    
    # Strip extra whitespace or lingering hyphens/colons
    cleaned = cleaned.strip(" -:–\t\n")
    return cleaned if cleaned else raw_name.strip()

def extract_subjects_and_dates(content_text):
    system_prompt = (
        "You are an expert academic schedule parser. Your goal is to extract only the human-readable FULL SUBJECT/COURSE NAMES from the timetable.\n\n"
        "STRICT EXTRACTION RULES:\n"
        "1. Extract ONLY the descriptive subject title (e.g., 'Operating Systems', 'Database Management Systems', 'Engineering Physics').\n"
        "2. STRICTLY IGNORE subject/course codes, alphanumeric IDs, and paper codes (e.g., DO NOT return 'CS301', 'PCC-CS501', 'MAT102', 'IT-601').\n"
        "3. If a line says 'CS401: Computer Networks', extract ONLY 'Computer Networks'.\n"
        "4. Filter out routine noise such as 'Lunch', 'Recess', 'Break', 'Library', 'TPO', 'Mentor Mentee'.\n"
        "5. Return a clean, unique list of subject names and the date range.\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "subjects": ["Computer Networks", "Database Management Systems", "Calculus"],\n'
        '  "start_date": "YYYY-MM-DD or null",\n'
        '  "end_date": "YYYY-MM-DD or null"\n'
        "}\n"
        "Do not include markdown tags (no ```json or ```) or explanatory notes."
    )

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract only the full subject names (no codes) and date range from this timetable text:\n\n{content_text}"}
        ],
        max_tokens=2048,
        temperature=0.0
    )

    raw_content = response.choices[0].message.content.strip()

    # Clean markdown backticks if present
    if "```" in raw_content:
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]
        raw_content = raw_content.strip()

    parsed = json.loads(raw_content)
    
    # Secondary cleaning pass in Python to guarantee no lingering codes
    raw_subjects = parsed.get("subjects", [])
    filtered_subjects = []
    
    for subj in raw_subjects:
        clean_name = clean_subject_name(subj)
        # Avoid pure codes that slipped through (e.g. if cleaned is just numbers/codes)
        if clean_name and not re.fullmatch(r'[A-Z]{2,5}[-\s]?\d{2,4}', clean_name, re.IGNORECASE):
            filtered_subjects.append(clean_name)

    parsed["subjects"] = sorted(list(set(filtered_subjects)))
    return parsed

# 4. Helper function: Generate empty attendance DataFrame
def create_blank_attendance_matrix(subjects, start_date, end_date):
    # Generate business days (Monday to Friday, excluding Saturday and Sunday)
    date_range = pd.date_range(start=start_date, end=end_date, freq="B")

    df = pd.DataFrame(index=date_range)
    df["Date"] = df.index.strftime("%Y-%m-%d")
    df["Day"] = df.index.strftime("%A")

    # Add blank columns for each subject
    for subject in subjects:
        df[subject] = ""

    df = df.reset_index(drop=True)
    cols = ["Date", "Day"] + sorted(subjects)
    return df[cols]

# 5. UI Controls
uploaded_file = st.file_uploader("Upload Routine PDF", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    default_start = date.today()
    start_input = st.date_input("Semester Start Date", value=default_start)
with col2:
    default_end = default_start.replace(month=min(default_start.month + 4, 12)) if default_start.month <= 8 else default_start.replace(year=default_start.year + 1, month=(default_start.month + 4) % 12 or 12)
    end_input = st.date_input("Semester End Date", value=default_end)

if uploaded_file and st.button("Generate Blank Attendance Sheet"):
    if start_input > end_input:
        st.error("Error: Start Date cannot be after End Date.")
        st.stop()

    with st.spinner("Extracting subjects and building attendance template..."):
        try:
            pdf_text = extract_text_from_pdf(uploaded_file)
            if not pdf_text.strip():
                st.error("No readable text found in this PDF. Please ensure it is a digital PDF.")
                st.stop()

            # Extract metadata with LLM
            parsed_data = extract_subjects_and_dates(pdf_text)
            extracted_subjects = parsed_data.get("subjects", [])

            if not extracted_subjects:
                st.warning("No subjects could be detected automatically. Please check the PDF content.")
                st.stop()

            # Use UI dates or model-detected dates
            final_start = parsed_data.get("start_date") or start_input
            final_end = parsed_data.get("end_date") or end_input

            # Build blank matrix
            df_matrix = create_blank_attendance_matrix(extracted_subjects, final_start, final_end)

            st.success(f"Successfully generated tracker for {len(extracted_subjects)} subjects across {len(df_matrix)} working days!")
            st.dataframe(df_matrix, use_container_width=True)

            # Export to formatted Excel file
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_matrix.to_excel(writer, index=False, sheet_name="Attendance_Tracker")
            excel_data = excel_buffer.getvalue()

            st.download_button(
                label="📥 Download Blank Attendance Excel Sheet",
                data=excel_data,
                file_name="student_attendance_tracker.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error generating attendance sheet: {e}")