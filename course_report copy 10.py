# all working including patient info AI treatment recommentations, patient case history analysis and table pagination
import pdfplumber
import io
import streamlit as st
import re
from pathlib import Path
import pandas as pd
from anthropic import Anthropic
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

def analyze_case_history(case_history, course_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        prompt = f"""Based on the patient's case history and ReOxy treatment results, identify key correlations and relevant clinical insights in 2-3 sentences.

        Case History:
        {case_history}

        Treatment Data:
        - Total Treatments: {len(course_data['treatments'])}
        - SpO2 Range: {course_data['treatments'][1].get('min_spo2_average', 'N/A')} - {course_data['treatments'][1].get('max_spo2_average', 'N/A')}
        """
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,  # Reduced token limit for more concise response
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing case history: {str(e)}"

def compare_sessions(course_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        sessions_data = []
        
        for treatment_num, data in course_data['treatments'].items():
            # Extract key metrics
            sessions_data.append(f"""
            Session {treatment_num}:
            Treatment Metrics:
            - Min SpO2 Av. (%): {data.get('Min SpO2 Av. (%)', 'N/A')}
            - Max SpO2 Av. (%): {data.get('Max SpO2 Av. (%)', 'N/A')}
            - Therapeutic SpO2 (%): {data.get('Therapeutic SpO2 (%)', 'N/A')}
            - Min PR Av. (bpm): {data.get('Min PR Av. (bpm)', 'N/A')}
            - Max PR Av. (bpm): {data.get('Max PR Av. (bpm)', 'N/A')}
            - Procedure duration (min:sec): {data.get('Procedure duration (min:sec)', 'N/A')}
            - Number of cycles: {data.get('Number of cycles', 'N/A')}
            - Hypoxic O2 conc. (%): {data.get('Hypoxic O2 conc. (%)', 'N/A')}
            """)

        prompt = f"""Analyze the following ReOxy treatment sessions and provide insights on:
        1. Changes in SpO2 tolerance and adaptation between sessions
        2. Heart rate response patterns and cardiovascular adaptation
        3. Changes in treatment duration and number of cycles
        4. Overall progression in hypoxic tolerance
        
        Treatment Data:{''.join(sessions_data)}
        
        Provide a concise analysis highlighting key trends, improvements, or areas of note between sessions."""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def generate_treatment_recommendations(course_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        sessions_data = []
        
        for treatment_num, data in course_data['treatments'].items():
            sessions_data.append(f"""
            Session {treatment_num}:
            Treatment Metrics:
            - Min SpO2 Av. (%): {data.get('Min SpO2 Av. (%)', 'N/A')}
            - Max SpO2 Av. (%): {data.get('Max SpO2 Av. (%)', 'N/A')}
            - Therapeutic SpO2 (%): {data.get('Therapeutic SpO2 (%)', 'N/A')}
            - Min PR Av. (bpm): {data.get('Min PR Av. (bpm)', 'N/A')}
            - Max PR Av. (bpm): {data.get('Max PR Av. (bpm)', 'N/A')}
            - Procedure duration (min:sec): {data.get('Procedure duration (min:sec)', 'N/A')}
            - Number of cycles: {data.get('Number of cycles', 'N/A')}
            - Hypoxic O2 conc. (%): {data.get('Hypoxic O2 conc. (%)', 'N/A')}
            """)

        prompt = f"""Based on the following ReOxy treatment sessions data, provide specific recommendations for future treatments. Consider:
        1. Whether to adjust hypoxic oxygen concentration
        2. Suggestions for treatment duration and number of cycles
        3. Target SpO2 ranges based on patient's adaptation
        4. Safety considerations based on observed responses
        
        Treatment Data:{''.join(sessions_data)}
        
        Provide 3-4 specific, actionable recommendations for optimizing future treatments."""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

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
            
            # Create a container for the selection interface
            selection_container = st.container()
            with selection_container:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader("Select Treatments")
                with col2:
                    st.write(f"Found: {len(treatment_numbers)}")
            
            # Custom CSS to make checkboxes more compact
            st.markdown("""
                <style>
                    div[data-testid="stHorizontalBlock"] > div {
                        padding: 0px !important;
                        margin: 0px !important;
                    }
                    div[data-testid="stHorizontalBlock"] {
                        gap: 0rem !important;
                        padding: 0px !important;
                        margin: 0px !important;
                    }
                    div.row-widget.stCheckbox {
                        padding: 0px !important;
                        margin: 0px !important;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            # Create columns for inline checkboxes (more columns for denser layout)
            num_cols = min(len(treatment_numbers), 8)  # Increased to 8 columns
            cols = st.columns(num_cols)
            
            # Update selected treatments without triggering analysis
            current_selections = []
            for i, treatment_num in enumerate(treatment_numbers):
                col_idx = i % num_cols
                if cols[col_idx].checkbox(str(treatment_num), 
                                        value=treatment_num in st.session_state.selected_treatments, 
                                        key=f"treatment_{treatment_num}",
                                        label_visibility="visible"):
                    current_selections.append(treatment_num)
            
            # Update selections in session state
            st.session_state.selected_treatments = current_selections
            
            # Add analyze button
            st.button("Process Selected Treatments", 
                     disabled=len(st.session_state.selected_treatments) == 0,
                     key="analyze_button",
                     on_click=lambda: setattr(st.session_state, 'show_analysis', True) or 
                                    setattr(st.session_state, 'analyzed_treatments', 
                                    st.session_state.selected_treatments.copy()))
            
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
                    
                    # Add case history analysis if text was entered
                    if case_history.strip():
                        st.subheader("Case History Analysis")
                        history_analysis = analyze_case_history(case_history, analysis_data)
                        st.write(history_analysis)
                    
                    # Add a separator
                    st.markdown("---")
                    
                    # Add session comparison if there are multiple treatments
                    if len(filtered_treatments) > 1:
                        st.subheader("Session Comparison")
                        comparison = compare_sessions(analysis_data)
                        st.write(comparison)
                        
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
                    
                    # Add paginated detailed view
                    st.subheader("Detailed Treatment Overview")
                    if analysis_data['treatments']:
                        # Convert treatments to sorted list of tuples
                        sorted_treatments = sorted(analysis_data['treatments'].items())
                        
                        # Group treatments into sets of 5 (changed from 10)
                        sessions_per_page = 5
                        all_pages = []
                        current_page = []
                        
                        for i, (treatment_num, data) in enumerate(sorted_treatments, 1):
                            current_page.append((treatment_num, data))
                            if i % sessions_per_page == 0 or i == len(sorted_treatments):
                                all_pages.append(current_page)
                                current_page = []
                        
                        # Add any remaining treatments to the last page
                        if current_page:
                            all_pages.append(current_page)
                        
                        # Create tabs for each group of 5 (updated labels)
                        tab_labels = [f"Sessions {i*5-4}-{min(i*5, len(sorted_treatments))}" 
                                     for i in range(1, len(all_pages) + 1)]
                        tabs = st.tabs(tab_labels)
                        
                        # Define fields to display
                        fields = [
                            ('Date', 'Treatment Date'),
                            ('Procedure duration (min:sec)', 'Total Duration'),
                            ('total_hypoxic_time', 'Total Hypoxic Time'),
                            ('Number of cycles', 'Number of Cycles'),
                            ('Hypox. Phase dur. Av. (min:sec)', 'Hypoxic Phase Duration Average'),
                            ('Min SpO2 Av. (%)', 'Min SpO2 Average'),
                            ('Hyperox. Phase dur. Av. (min:sec)', 'Hyperoxic Phase Duration Average'),
                            ('Max SpO2 Av. (%)', 'Max SpO2 Average'),
                            ('Min PR Av. (bpm)', 'Min PR Average'),
                            ('Max PR Av. (bpm)', 'Max PR Average'),
                            ('Therapeutic SpO2 (%)', 'Therapeutic SpO2'),
                            ('Hypoxic O2 conc. (%)', 'Hypoxic O2 Concentration'),
                            ('BP_before', 'BP Before Procedure'),
                            ('BP_after', 'BP After Procedure')
                        ]
                        
                        # Display content for each tab
                        for tab_index, tab in enumerate(tabs):
                            with tab:
                                current_treatments = all_pages[tab_index]
                                
                                # Create columns for the table
                                cols = st.columns(len(current_treatments) + 1)  # +1 for labels column
                                
                                # Treatment number headers
                                for i, (treatment_num, _) in enumerate(current_treatments, 1):
                                    cols[i].write(f"Session {treatment_num}")
                                
                                # Create rows
                                for field_key, field_label in fields:
                                    cols = st.columns(len(current_treatments) + 1)
                                    cols[0].write(field_label)
                                    for i, (treatment_num, data) in enumerate(current_treatments, 1):
                                        if field_key == 'BP_before':
                                            sys_before = data.get('BP SYS before (mmHg)', 'N/A')
                                            dia_before = data.get('BP DIA before (mmHg)', 'N/A')
                                            value = f"{sys_before}/{dia_before}" if sys_before != 'N/A' else 'N/A'
                                        elif field_key == 'BP_after':
                                            sys_after = data.get('BP SYS after (mmHg)', 'N/A')
                                            dia_after = data.get('BP DIA after (mmHg)', 'N/A')
                                            value = f"{sys_after}/{dia_after}" if sys_after != 'N/A' else 'N/A'
                                        else:
                                            value = df.loc[treatment_num, field_key] if field_key in df.columns else data.get(field_key, 'N/A')
                                        cols[i].write(value)
                    
                    # Add treatment recommendations section
                    st.subheader("Treatment Recommendations")
                    with st.spinner('Generating treatment recommendations...'):
                        recommendations = generate_treatment_recommendations(analysis_data)
                        st.write(recommendations)

if __name__ == "__main__":
    main() 