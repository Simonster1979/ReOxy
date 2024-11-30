$# Just missing BP information
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
                    
                    # Debug output for BP table detection
                    st.write("\nChecking table headers:", headers)
                    if any("BP" in str(cell) for cell in headers):
                        st.write("Found BP table!")
                        st.write("Processing rows:")
                        for row in table:
                            st.write(row)
                    
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
                                values = []
                                # Collect all values first
                                for value in row[1:]:
                                    if value and value.strip():
                                        values.append(value.strip())
                                
                                # Match values with correct treatment numbers
                                for i, treatment_num in enumerate(treatment_nums):
                                    if i < len(values):
                                        course_data['treatments'][treatment_num][matched_measure] = values[i]
                    
                    # Process BP measurements table
                    elif any("BP" in str(cell) for cell in headers):
                        current_treatment = None
                        bp_mappings = {
                            "BP SYS before": "BP SYS before (mmHg)",
                            "BP DIA before": "BP DIA before (mmHg)",
                            "BP SYS after": "BP SYS after (mmHg)",
                            "BP DIA after": "BP DIA after (mmHg)"
                        }
                        
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
                                for bp_pattern, full_name in bp_mappings.items():
                                    if bp_pattern in measure_name:
                                        value = str(row[1]).strip()
                                        course_data['treatments'][current_treatment][full_name] = value
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