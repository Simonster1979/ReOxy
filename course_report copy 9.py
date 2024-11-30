# all working including selecting individual treatments to run
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
    return None

def main():
    st.title("Course Report PDF Extractor")
    
    # Initialize session state
    if 'course_data' not in st.session_state:
        st.session_state.course_data = None
    if 'selected_treatments' not in st.session_state:
        st.session_state.selected_treatments = []
    if 'show_analysis' not in st.session_state:
        st.session_state.show_analysis = False
    if 'analyzed_treatments' not in st.session_state:
        st.session_state.analyzed_treatments = []
    
    # Add case history text area
    case_history = st.text_area(
        "Patient Case History",
        height=150,
        help="Enter relevant patient history, conditions, medications, and other clinical notes"
    )
    
    # Add a separator
    st.markdown("---")
    
    uploaded_file = st.file_uploader(
        "Upload Course Report PDF", 
        type="pdf",
        accept_multiple_files=False,
        key="pdf_uploader"
    )
    
    if uploaded_file:
        # Only extract data if it hasn't been extracted yet
        if st.session_state.course_data is None:
            with st.spinner('Loading report...'):
                try:
                    st.session_state.course_data = extract_course_report(uploaded_file)
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    return
        
        if st.session_state.course_data:
            treatment_numbers = sorted(st.session_state.course_data['treatments'].keys())
            
            st.subheader("Select Treatments to Extract")
            st.write(f"Found {len(treatment_numbers)} treatments in the report.")
            
            # Create columns for inline checkboxes
            num_cols = min(len(treatment_numbers), 5)  # Max 5 columns per row
            cols = st.columns(num_cols)
            
            # Update selected treatments without triggering analysis
            current_selections = []
            for i, treatment_num in enumerate(treatment_numbers):
                col_idx = i % num_cols
                if cols[col_idx].checkbox(f"Treatment {treatment_num}", 
                                        value=treatment_num in st.session_state.selected_treatments, 
                                        key=f"treatment_{treatment_num}"):
                    current_selections.append(treatment_num)
            
            # Update selections in session state
            st.session_state.selected_treatments = current_selections
            
            # Add analyze button
            if st.button("Process Selected Treatments", 
                        disabled=len(st.session_state.selected_treatments) == 0,
                        key="analyze_button"):
                st.session_state.show_analysis = True
                st.session_state.analyzed_treatments = st.session_state.selected_treatments.copy()
            
            # Show analysis only if button was clicked and using the analyzed treatments
            if st.session_state.show_analysis and st.session_state.analyzed_treatments:
                st.markdown("---")
                with st.spinner('Processing selected treatments...'):
                    # Filter course_data to only include analyzed treatments
                    filtered_treatments = {k: v for k, v in st.session_state.course_data['treatments'].items() 
                                        if k in st.session_state.analyzed_treatments}
                    analysis_data = st.session_state.course_data.copy()
                    analysis_data['treatments'] = filtered_treatments
                    
                    # Display patient information first
                    st.subheader("Patient Information")
                    st.write(f"**Patient Name:** {analysis_data['patient_name']}")
                    st.write(f"**Date of Birth:** {analysis_data['dob']}")
                    st.write(f"**Sex:** {analysis_data['sex']}")
                    
                    # Add a separator
                    st.markdown("---")
                    
                    # Show comparison table
                    st.subheader("Treatment Overview")
                    df = pd.DataFrame.from_dict(analysis_data['treatments'], orient='index')
                    if analysis_data['schedule']:
                        df['Date'] = df.index.map(lambda x: analysis_data['schedule'].get(x, ''))
                        cols = ['Date'] + [col for col in df.columns if col != 'Date']
                        df = df[cols]
                    
                    st.dataframe(df)

if __name__ == "__main__":
    main() 