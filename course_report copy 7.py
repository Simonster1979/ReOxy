# all working including patient info now need to parse to app.py
import pdfplumber
import io
import streamlit as st
import re
from pathlib import Path
import pandas as pd

st.set_page_config(layout="wide")

def extract_course_report(pdf_file):
    """
    Extract text from course report PDF
    
    Args:
        pdf_file: File object containing the PDF
        
    Returns:
        dict: Extracted course report data
    """
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        
        course_data = {
            'patient_name': '',
            'sex': '',
            'dob': '',
            'raw_text': '',
            'word_list': [],
            'schedule': {},
            'treatments': {}
        }
        
        # Extract all text from the first page first
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        course_data['raw_text'] = text
        
        # Extract patient info from raw text using regex
        name_match = re.search(r'Ref\. No\.\s+([A-Za-z\s]+?)(?=\s+(?:Female|Male))', text)
        if name_match:
            course_data['patient_name'] = name_match.group(1).strip()
            
        sex_match = re.search(r'(?:Female|Male)', text)
        if sex_match:
            course_data['sex'] = sex_match.group(0).strip()
            
        birth_match = re.search(r'(?:Female|Male)\s+(\d{2}\.\d{2}\.\d{4})', text)
        if birth_match:
            course_data['dob'] = birth_match.group(1).strip()
        
        for page in pdf.pages:
            tables = page.extract_tables()
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=2,
                keep_blank_chars=True,
                use_text_flow=False,
                split_at_punctuation=False
            )
            
            word_list = [w['text'].strip() for w in words]
            course_data['word_list'] = word_list
            
            # Process schedule table first
            for table in tables:
                if table and len(table) > 0:
                    # Look for rows that contain treatment dates
                    for row in table:
                        if not row:
                            continue
                        
                        # Process pairs of treatment and date
                        for i in range(0, len(row), 2):
                            if i + 1 >= len(row):
                                break
                            
                            treatment_text = str(row[i]).strip()
                            date_text = str(row[i + 1]).strip()
                            
                            if treatment_text.startswith("Treatment"):
                                try:
                                    # Strip any non-numeric characters before converting to int
                                    treatment_num = int(''.join(filter(str.isdigit, treatment_text)))
                                    if date_text:
                                        course_data['schedule'][treatment_num] = date_text
                                except (ValueError, IndexError):
                                    continue
            
            # Process tables for treatment data
            for table in tables:
                if table and len(table) > 0:
                    headers = table[0] if table else []
                    
                    # Process main treatment table (with SpO2, PR, etc.)
                    if "Treatment No." in str(headers) and not any("BP" in str(row[0]) for row in table if row and row[0]):
                        # Process main treatment measurements table
                        treatment_nums = []
                        for cell in headers[1:]:
                            try:
                                if cell and cell.strip():
                                    num = int(cell.strip())
                                    treatment_nums.append(num)
                                    if num not in course_data['treatments']:
                                        course_data['treatments'][num] = {}
                            except ValueError:
                                continue
                        
                        # Process each measurement row
                        for row in table[1:]:
                            if not row or not row[0]:
                                continue
                            
                            measure_name = str(row[0]).strip()
                            
                            # Special handling for Hypoxic O2 conc.
                            if "Hypoxic O" in measure_name:
                                for i, value in enumerate(row[1:]):
                                    if i < len(treatment_nums) and value and value.strip():
                                        treatment_num = treatment_nums[i]
                                        course_data['treatments'][treatment_num]["Hypoxic O2 conc. (%)"] = value.strip()
                                continue
                            
                            # Regular measurement mappings for other values
                            measure_mappings = {
                                "Min SpO": "Min SpO2 Av. (%)",
                                "Max SpO": "Max SpO2 Av. (%)",
                                "Therapeutic SpO": "Therapeutic SpO2 (%)",
                                "Procedure duration": "Procedure duration (min:sec)",
                                "Hypox. Phase dur": "Hypox. Phase dur. Av. (min:sec)",
                                "Hyperox. Phase dur": "Hyperox. Phase dur. Av. (min:sec)",
                                "Number of cycles": "Number of cycles",
                                "Min PR": "Min PR Av. (bpm)",
                                "Max PR": "Max PR Av. (bpm)"
                            }
                            
                            # Process measurements
                            matched_measure = None
                            for pattern, full_name in measure_mappings.items():
                                if pattern in measure_name:
                                    matched_measure = full_name
                                    break
                            
                            if matched_measure:
                                for i, value in enumerate(row[1:]):
                                    if i < len(treatment_nums) and value and value.strip():
                                        treatment_num = treatment_nums[i]
                                        course_data['treatments'][treatment_num][matched_measure] = value.strip()
                    
                    # Process BP table separately
                    elif any("BP" in str(row[0]) for row in table if row and row[0]):
                        # Get treatment numbers from first row
                        treatment_nums = []
                        for cell in headers[1:]:
                            try:
                                if cell and cell.strip():
                                    num = int(cell.strip())
                                    treatment_nums.append(num)
                                    if num not in course_data['treatments']:
                                        course_data['treatments'][num] = {}
                            except ValueError:
                                continue
                        
                        # Process each BP measurement row
                        for row in table[1:]:
                            if not row or not row[0]:
                                continue
                            
                            measure_name = str(row[0]).strip()
                            # Process each value in the row
                            for i, value in enumerate(row[1:]):
                                if i < len(treatment_nums) and value and value.strip():
                                    treatment_num = treatment_nums[i]
                                    course_data['treatments'][treatment_num][measure_name] = value.strip()
        
        # Add pattern matching for patient info near the start
        for word_idx, word in enumerate(word_list):
            # Look for patient name pattern
            if word.lower() == "name:":
                try:
                    course_data['patient_name'] = word_list[word_idx + 1]
                except IndexError:
                    pass
            
            # Look for sex
            if word.lower() == "sex:":
                try:
                    course_data['sex'] = word_list[word_idx + 1]
                except IndexError:
                    pass
                
            # Look for date of birth
            if word.lower() == "birth:":
                try:
                    course_data['dob'] = word_list[word_idx + 1]
                except IndexError:
                    pass
        
        return course_data
        
    except Exception as e:
        raise Exception(f"Error extracting course report: {str(e)}")

def load_default_pdf():
    """Load the default Course Report.pdf file"""
    default_path = Path("Course Report.pdf")
    if default_path.exists():
        return open(default_path, "rb")
    return None

def main():
    st.title("Course Report PDF Extractor")
    
    default_file = load_default_pdf()
    uploaded_file = st.file_uploader(
        "Upload Course Report PDF", 
        type="pdf",
        accept_multiple_files=False
    )
    
    pdf_file = uploaded_file if uploaded_file else default_file
    
    if pdf_file:
        try:
            course_data = extract_course_report(pdf_file)
            
            # Display patient information first
            st.subheader("Patient Information")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Name:** {course_data['patient_name']}")
            with col2:
                st.write(f"**Sex:** {course_data['sex']}")
            with col3:
                st.write(f"**Date of Birth:** {course_data['dob']}")
            
            # Show comparison table
            st.subheader("Comparison Table")
            df = pd.DataFrame.from_dict(course_data['treatments'], orient='index')
            if course_data['schedule']:
                # Add date column if schedule data exists
                df['Date'] = df.index.map(lambda x: course_data['schedule'].get(x, ''))
                # Reorder columns to put date first
                cols = ['Date'] + [col for col in df.columns if col != 'Date']
                df = df[cols]
            
            st.dataframe(df)
            
            # Hide Treatment Data section
            # st.subheader("Treatment Data")
            # for treatment_num in sorted(course_data['treatments'].keys()):
            #     st.write(f"\nTreatment {treatment_num}:")
            #     if treatment_num in course_data['schedule']:
            #         st.write(f"Date: {course_data['schedule'][treatment_num]}")
            #     measurements = [
            #         "Hypoxic O2 conc. (%)",
            #         "Procedure duration (min:sec)",
            #         "Therapeutic SpO2 (%)",
            #         "Hypox. Phase dur. Av. (min:sec)",
            #         "Hyperox. Phase dur. Av. (min:sec)",
            #         "Number of cycles",
            #         "Min SpO2 Av. (%)",
            #         "Max SpO2 Av. (%)",
            #         "Min PR Av. (bpm)",
            #         "Max PR Av. (bpm)",
            #         "BP SYS before (mmHg)",
            #         "BP DIA before (mmHg)",
            #         "BP SYS after (mmHg)",
            #         "BP DIA after (mmHg)"
            #     ]
            #     for measure in measurements:
            #         if measure in course_data['treatments'][treatment_num]:
            #             st.write(f"{measure}: {course_data['treatments'][treatment_num][measure]}")
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 