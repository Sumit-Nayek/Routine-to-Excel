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
import re
from datetime import date
from io import BytesIO
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from huggingface_hub import InferenceClient
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Attendance & Holiday Tracker", page_icon="📝", layout="wide")
st.title("📝 Student Attendance & Holiday Tracker Generator")
st.write("Upload your Routine and optional Academic Holiday Calendar to generate an attendance tracker with highlighted off-days.")

# 1. Retrieve Hugging Face Token securely
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    st.error("HF_TOKEN not detected in environment variables. Run: export HF_TOKEN='your_token'")
    st.stop()

client = InferenceClient(api_key=HF_TOKEN)

# 2. PDF Text Extractor Helper
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    extracted_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"
    return extracted_text

# 3. Regex Subject Name Cleaner
def clean_subject_name(raw_name: str) -> str:
    cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_name)
    cleaned = re.sub(r'^[A-Z]{2,5}[-\s]?\d{2,4}\s*[:\-–]?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*[:\-–]?\s*[A-Z]{2,5}[-\s]?\d{2,4}$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -:–\t\n")
    return cleaned if cleaned else raw_name.strip()

# 4. Extract Subjects from Routine PDF
def extract_routine_subjects(routine_text):
    system_prompt = (
        "You are an academic routine parser. Extract ONLY the human-readable subject names.\n"
        "STRICT RULES:\n"
        "1. Extract full descriptive subject names (e.g., 'Operating Systems', 'Calculus', 'Thermodynamics').\n"
        "2. STRICTLY IGNORE subject/paper codes (e.g., DO NOT return 'CS301', 'PCC-CS501', 'MAT102').\n"
        "3. Ignore generic labels like 'Lunch', 'Break', 'Library', 'Mentor Mentee'.\n"
        "Return ONLY a JSON object: {\"subjects\": [\"Subject 1\", \"Subject 2\"]}"
    )

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract unique subjects from this timetable:\n\n{routine_text}"}
        ],
        max_tokens=2048,
        temperature=0.0
    )

    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()

    parsed = json.loads(raw)
    cleaned = [clean_subject_name(s) for s in parsed.get("subjects", []) if clean_subject_name(s)]
    return sorted(list(set(cleaned)))

# 5. Extract Holidays from Holiday PDF
def extract_holidays(holiday_text):
    system_prompt = (
        "You are an academic calendar parser. Extract all listed institutional holidays and off-days.\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{\n"
        '  "holidays": [\n'
        '    {"date": "YYYY-MM-DD", "occasion": "Independence Day"}\n'
        "  ]\n"
        "}\n"
        "Do not include extra markdown ticks or notes. Only output valid JSON."
    )

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract holiday dates and their names from this academic calendar:\n\n{holiday_text}"}
        ],
        max_tokens=2048,
        temperature=0.0
    )

    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()

    parsed = json.loads(raw)
    # Convert list into a date -> occasion dictionary
    return {h["date"]: h.get("occasion", "Holiday") for h in parsed.get("holidays", []) if "date" in h}

# 6. Generate Formatted Excel with OpenPyXL
def generate_excel_with_highlights(subjects, holidays, start_date, end_date):
    # Weekdays only (Monday through Friday)
    date_range = pd.date_range(start=start_date, end=end_date, freq="B")
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance_Tracker"

    # Styling definitions
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    holiday_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Soft Orange/Red
    holiday_font = Font(name="Calibri", size=10, italic=True, color="C00000")
    
    # Headers
    headers = ["Date", "Day", "Remarks"] + subjects
    ws.append(headers)

    # Style Header Row
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Populate Dates
    for row_idx, dt in enumerate(date_range, start=2):
        date_str = dt.strftime("%Y-%m-%d")
        day_str = dt.strftime("%A")
        holiday_name = holidays.get(date_str, "")
        
        row_data = [date_str, day_str, holiday_name] + [""] * len(subjects)
        ws.append(row_data)

        # If it's a holiday, highlight the entire row
        if holiday_name:
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.fill = holiday_fill
                if col_idx == 3: # Remarks column
                    cell.font = holiday_font

    # Set column widths for clean readability
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 25
    for col_letter in [openpyxl.utils.get_column_letter(i) for i in range(4, len(headers) + 1)]:
        ws.column_dimensions[col_letter].width = 22

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

# --- Streamlit UI ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    routine_file = st.file_uploader("1. Upload Routine PDF (Mandatory)", type=["pdf"])
with col_u2:
    holiday_file = st.file_uploader("2. Upload Holiday Calendar PDF (Optional)", type=["pdf"])

col_d1, col_d2 = st.columns(2)
with col_d1:
    default_start = date.today()
    start_input = st.date_input("Semester Start Date", value=default_start)
with col_d2:
    default_end = default_start.replace(month=min(default_start.month + 4, 12)) if default_start.month <= 8 else default_start.replace(year=default_start.year + 1, month=(default_start.month + 4) % 12 or 12)
    end_input = st.date_input("Semester End Date", value=default_end)

if routine_file and st.button("Generate Attendance Sheet"):
    if start_input > end_input:
        st.error("Start Date cannot be after End Date.")
        st.stop()

    with st.spinner("Processing documents and building attendance tracker..."):
        try:
            # 1. Parse Routine
            routine_text = extract_text_from_pdf(routine_file)
            subjects = extract_routine_subjects(routine_text)
            if not subjects:
                st.error("No subjects could be detected from the routine. Please check the PDF.")
                st.stop()

            # 2. Parse Holidays (if uploaded)
            holidays = {}
            if holiday_file:
                holiday_text = extract_text_from_pdf(holiday_file)
                holidays = extract_holidays(holiday_text)
                st.info(f"Detected {len(holidays)} academic holidays.")

            # 3. Generate Highlighted Excel
            excel_data = generate_excel_with_highlights(subjects, holidays, start_input, end_input)

            st.success("Attendance Tracker generated successfully!")
            st.download_button(
                label="📥 Download Excel Tracker (with Holiday Highlights)",
                data=excel_data,
                file_name="attendance_tracker_with_holidays.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error during processing: {e}")