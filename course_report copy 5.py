#almost perfect just need the treatment date to line up

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
            tables = page.extract_tables()
            
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
            
            # Display treatment data with all measurements including BP
            st.subheader("Treatment Data")
            for treatment_num in sorted(course_data['treatments'].keys()):
                st.write(f"\nTreatment {treatment_num}:")
                measurements = [
                    "Hypoxic O2 conc. (%)",
                    "Procedure duration (min:sec)",
                    "Therapeutic SpO2 (%)",
                    "Hypox. Phase dur. Av. (min:sec)",
                    "Hyperox. Phase dur. Av. (min:sec)",
                    "Number of cycles",
                    "Min SpO2 Av. (%)",
                    "Max SpO2 Av. (%)",
                    "Min PR Av. (bpm)",
                    "Max PR Av. (bpm)",
                    "BP SYS before (mmHg)",
                    "BP DIA before (mmHg)",
                    "BP SYS after (mmHg)",
                    "BP DIA after (mmHg)"
                ]
                
                for measure in measurements:
                    if measure in course_data['treatments'][treatment_num]:
                        st.write(f"  {measure}: {course_data['treatments'][treatment_num][measure]}")
            
            # Create DataFrame for comparison
            df = pd.DataFrame.from_dict(course_data['treatments'], orient='index')
            st.subheader("Comparison Table")
            st.dataframe(df)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 