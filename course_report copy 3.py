#better again
import pdfplumber
import io
import streamlit as st
import re
from pathlib import Path
import pandas as pd

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
        
        for page in pdf.pages:
            # Extract both tables and words
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
            
            # Add debugging output
            st.write("Raw Tables Found:")
            for i, table in enumerate(tables):
                st.write(f"\nTable {i + 1}:")
                for row in table:
                    st.write(row)
            
            # Process tables for treatment data
            for table in tables:
                if table and len(table) > 0:
                    headers = table[0] if table else []
                    
                    # Check for treatment table
                    if "Treatment No." in str(headers):
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
                                "Therapeutic SpO": "Therapeutic SpO2 (%)",
                                "Procedure duration": "Procedure duration (min:sec)",
                                "Hypox. Phase dur": "Hypox. Phase dur. Av. (min:sec)",
                                "Hyperox. Phase dur": "Hyperox. Phase dur. Av. (min:sec)",
                                "Number of cycles": "Number of cycles"
                            }
                            
                            # Process other measurements
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
                    
                    # Process BP measurements table
                    elif any("BP" in str(cell) for cell in headers):
                        current_treatment = None
                        for row in table:
                            if not row:
                                continue
                            
                            # Check for treatment number
                            first_cell = str(row[0]).strip()
                            if first_cell.startswith("Treatment"):
                                try:
                                    current_treatment = int(first_cell.split()[-1])
                                    if current_treatment not in course_data['treatments']:
                                        course_data['treatments'][current_treatment] = {}
                                except ValueError:
                                    continue
                            
                            # Process BP measurements
                            if current_treatment and len(row) >= 2:
                                measure_name = str(row[0]).strip()
                                if any(bp in measure_name for bp in ["BP SYS", "BP DIA"]):
                                    value = str(row[1]).strip()
                                    course_data['treatments'][current_treatment][measure_name] = value
            
            # Process schedule section
            in_schedule = False
            for i, word in enumerate(word_list):
                if word == "Schedule":
                    in_schedule = True
                    continue
                    
                if in_schedule and word.startswith("Treatment"):
                    try:
                        # Extract treatment number
                        treatment_num = int(word.split()[-1])
                        # Look ahead for date
                        if i + 1 < len(word_list):
                            date = word_list[i + 1]
                            course_data['schedule'][treatment_num] = date
                            # Initialize treatments dict
                            if treatment_num not in course_data['treatments']:
                                course_data['treatments'][treatment_num] = {}
                    except ValueError:
                        continue
                
                # End of schedule section (you might want to adjust this condition)
                if in_schedule and word == "Patient name":
                    in_schedule = False
            
            # Process treatment section
            for i, word in enumerate(word_list):
                if word == "Treatment" and i + 1 < len(word_list) and word_list[i + 1] == "No.":
                    treatment_data = process_treatment_section(word_list, i)
                    course_data['treatments'].update(treatment_data)
                    break
            
            # Process the word list to build relationships
            current_treatment = None
            current_header = None
            
            for i, word in enumerate(word_list):
                # Extract patient info
                if "Patient name" in word and i + 4 < len(word_list):
                    course_data['patient_name'] = word_list[i + 4]
                elif "Sex" in word and i + 4 < len(word_list):
                    course_data['sex'] = word_list[i + 4]
                elif "Date of birth" in word and i + 4 < len(word_list):
                    course_data['dob'] = word_list[i + 4]
                
                # Track treatment numbers
                elif word == "Treatment No.":
                    current_header = "Treatment No."
                    # Look ahead for treatment numbers
                    j = i + 1
                    while j < len(word_list):
                        try:
                            treatment_num = int(word_list[j])
                            if treatment_num not in course_data['treatments']:
                                course_data['treatments'][treatment_num] = {}
                            j += 1
                        except ValueError:
                            break
                
                # Process measurements
                elif word in ["Hypoxic O2 conc. (%)", "Min SpO2 Av. (%)", "Max SpO2 Av. (%)", 
                            "Min PR Av. (bpm)", "Max PR Av. (bpm)"]:
                    current_header = word
                    # Look ahead for values
                    j = i + 1
                    treatment_index = 0
                    while j < len(word_list):
                        try:
                            value = word_list[j]
                            # Try to convert to number (integer or float)
                            float(value)
                            # Find corresponding treatment number
                            treatment_nums = sorted(course_data['treatments'].keys())
                            if treatment_index < len(treatment_nums):
                                treatment_num = treatment_nums[treatment_index]
                                course_data['treatments'][treatment_num][current_header] = value
                            treatment_index += 1
                            j += 1
                        except ValueError:
                            break
            
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
            
            # Display schedule information
            st.subheader("Schedule")
            for treatment_num in sorted(course_data['schedule'].keys()):
                st.write(f"Treatment {treatment_num}: {course_data['schedule'][treatment_num]}")
            
            # Display patient information
            st.subheader("Patient Information")
            st.write(f"Patient Name: {course_data['patient_name']}")
            st.write(f"Sex: {course_data['sex']}")
            st.write(f"Date of Birth: {course_data['dob']}")
            
            # Display treatment data
            st.subheader("Treatment Data")
            for treatment_num in sorted(course_data['treatments'].keys()):
                st.write(f"\nTreatment {treatment_num}:")
                for measure, value in course_data['treatments'][treatment_num].items():
                    st.write(f"  {measure}: {value}")
            
            # Create DataFrame for comparison
            df = pd.DataFrame.from_dict(course_data['treatments'], orient='index')
            st.subheader("Comparison Table")
            st.dataframe(df)
            
            # Display raw word list with indices (for debugging)
            st.subheader("Raw Word List")
            for i, word in enumerate(course_data['word_list']):
                st.text(f"{i}: {word}")
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 