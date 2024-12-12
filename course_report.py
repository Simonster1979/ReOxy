# all working now working on uploading and removing pdf errors and login
import pdfplumber
import io
import streamlit as st
import re
from pathlib import Path
import pandas as pd
#from anthropic import Anthropic
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from openai import OpenAI

# Load environment variables
load_dotenv()

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

def analyze_case_history(case_history, analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Get treatment metrics for analysis
        treatment_data = []
        for treatment_num, data in sorted(analysis_data['treatments'].items()):
            treatment_data.append(f"""
            Session {treatment_num}:
            - SpO2 Range: {data.get('Min SpO2 Av. (%)', 'N/A')} - {data.get('Max SpO2 Av. (%)', 'N/A')}
            - PR Range: {data.get('Min PR Av. (bpm)', 'N/A')} - {data.get('Max PR Av. (bpm)', 'N/A')}
            - Hypoxic Phase Duration: {data.get('Hypox. Phase dur. Av. (min:sec)', 'N/A')}
            - Number of Cycles: {data.get('Number of cycles', 'N/A')}
            - BP Before: {data.get('BP SYS before (mmHg)', 'N/A')}/{data.get('BP DIA before (mmHg)', 'N/A')}
            - BP After: {data.get('BP SYS after (mmHg)', 'N/A')}/{data.get('BP DIA after (mmHg)', 'N/A')}
            """)
        
        prompt = f"""Based on the patient's case history and ReOxy treatment results, identify key correlations and relevant clinical insights in 2-3 sentences.

        Case History:
        {case_history}

        Treatment Data:
        - Total Sessions: {len(analysis_data['treatments'])}
        - Patient Name: {analysis_data.get('patient_name', 'N/A')}
        - Sex: {analysis_data.get('sex', 'N/A')}
        - Date of Birth: {analysis_data.get('dob', 'N/A')}

        Detailed Treatment Results:
        {''.join(treatment_data)}

        Please analyze:
        1. How the patient's medical history relates to their treatment responses
        2. Any patterns in vital signs that correlate with their medical history
        3. Potential implications for future treatment based on history and responses
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing case history: {str(e)}"

def analyze_phase_durations(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted(analysis_data['treatments'].items()):
            sessions_data.append(f"""
            Session {treatment_num}:
            - Hyperoxic Phase Duration: {data.get('Hyperox. Phase dur. Av. (min:sec)', 'N/A')}
            - Hypoxic Phase Duration: {data.get('Hypox. Phase dur. Av. (min:sec)', 'N/A')}
            """)
        
        prompt = f"""Analyze the hyperoxic and hypoxic phase duration trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between hyperoxic and hypoxic durations
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing phase durations: {str(e)}"

def analyze_pr_trends(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted(analysis_data['treatments'].items()):
            sessions_data.append(f"""
            Session {treatment_num}:
            - Min PR Average: {data.get('Min PR Av. (bpm)', 'N/A')}
            - Max PR Average: {data.get('Max PR Av. (bpm)', 'N/A')}
            """)
        
        prompt = f"""Analyze the Pulse Rate averages trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between Min and Max Pulse Rate averages
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing pulse rate trends: {str(e)}"

def analyze_hypoxic_time(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted(analysis_data['treatments'].items()):
            sessions_data.append(f"""
            Session {treatment_num}:
            - Total Hypoxic Time: {data.get('total_hypoxic_calc', 'N/A')}
            - Number of cycles: {data.get('Number of cycles', 'N/A')}
            - Min SpO2: {data.get('Min SpO2 Av. (%)', 'N/A')}
            """)
        
        prompt = f"""Analyze the total hypoxic time trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. Changes in hypoxic exposure duration
        2. What this suggests about the patient's adaptation to hypoxic stress

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing hypoxic time: {str(e)}"

def analyze_bp_trends(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted(analysis_data['treatments'].items()):
            sessions_data.append(f"""
            Session {treatment_num}:
            - BP Before: {data.get('BP SYS before (mmHg)', 'N/A')}/{data.get('BP DIA before (mmHg)', 'N/A')}
            - BP After: {data.get('BP SYS after (mmHg)', 'N/A')}/{data.get('BP DIA after (mmHg)', 'N/A')}
            """)
        
        prompt = f"""Analyze the blood pressure response across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The acute BP response to each session (before vs after)
        2. The overall trend across sessions and what this suggests about cardiovascular adaptation

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing BP trends: {str(e)}"

def compare_sessions_openai(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sessions_data = []
        
        for treatment_num, data in analysis_data['treatments'].items():
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
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def main():
    # Replace the AI model selectbox with a hidden default
    ai_model = "Claude 3 Sonnet"  # Set default model
    
    st.title("Course Report PDF Extractor")
    
    # Add custom CSS for print styling
    st.markdown("""
        <style>
            @media print {
                /* Basic page setup */
                @page {
                    size: A4;
                    margin: 0.5cm;
                }

                /* Hide Streamlit UI elements */
                .stButton, .stDownloadButton, header, footer,
                .stFileUploader, [data-testid="stFileUploader"],
                [data-testid="stFileUploadDropzone"],
                .css-1p1nwyz,
                [data-testid="stSidebar"],
                section[data-testid="stSidebarContent"],
                .css-1d391kg,
                [data-testid="stExpander"],
                .streamlit-expanderHeader,
                .stDownloadButton,
                .patient-case-history,
                #tabs-bui30-tabpanel-0, .st-ev,
                [data-testid="stTextArea"], 
                .stTextArea > label,
                .detailed-overview-header,
                .detailed-overview-content {
                    display: none !important;
                }

                /* Typography */
                h1 {
                    font-size: 32pt !important;
                    font-weight: bold !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    line-height: 1.2 !important;
                }

                h2, .stSubheader {
                    font-size: 34pt !important;
                    font-weight: bold !important;
                    margin: 20px 0 10px 0 !important;
                }

                h3, .stMarkdown h3 {
                    font-size: 30pt !important;
                    font-weight: bold !important;
                }

                p, div, span, li, .stMarkdown p {
                    font-size: 26pt !important;
                    line-height: 1.4 !important;
                }

                strong, b, .field-label {
                    font-size: 24pt !important;
                    font-weight: bold !important;
                }

                /* Charts and Plots */
                .js-plotly-plot, .plotly {
                    max-height: 400px !important;
                    margin-bottom: 150px !important;
                    break-inside: avoid !important;
                }

                .js-plotly-plot .plotly text {
                    font-size: 20pt !important;
                }

                .legend text {
                    font-size: 18pt !important;
                }

                /* Layout and Spacing */
                .element-container {
                    break-inside: avoid !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .main .block-container,
                .css-1d391kg, .css-1544g2n, .css-18e3th9,
                .stMarkdown {
                    padding: 0 !important;
                    margin: 0 !important;
                }

                /* Keep content together */
                .case-history-section,
                .chart-container,
                tr, tbody {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                }

                thead {
                    display: table-header-group !important;
                }

                /* Custom spacing for myUniqueId */
                .myUniqueId {
                    margin: -700px 0 -900px 0;
                }

                /* Field values */
                .field-value {
                    font-size: 24pt !important;
                }

                /* Treatment headers */
                .treatment-header {
                    font-size: 28pt !important;
                }

                /* Detailed overview */
                .detailed-overview-header {
                    font-size: 30pt !important;
                    break-before: page !important;
                    break-after: avoid !important;
                }

                .detailed-overview-content {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'course_data' not in st.session_state:
        st.session_state.course_data = None
    if 'selected_treatments' not in st.session_state:
        st.session_state.selected_treatments = []
    if 'show_analysis' not in st.session_state:
        st.session_state.show_analysis = False
    if 'analyzed_treatments' not in st.session_state:
        st.session_state.analyzed_treatments = []
    
    # Wrap the case history section in a div with the print-hiding class
    with st.container():
        st.markdown('<div class="patient-case-history">', unsafe_allow_html=True)
        case_history = st.text_area(
            "Patient Case History",
            height=150,
            help="Enter relevant patient history, conditions, medications, and other clinical notes",
            key="course_report_case_history"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Add a separator
    st.markdown("---")
    
    uploaded_file = st.file_uploader(
        "Upload Course Report PDF", 
        type="pdf",
        accept_multiple_files=False,
        key="course_report_pdf_uploader"
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
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.subheader("Select Treatments")
                with col2:
                    st.markdown(f'<div class="treatment-count">Found: {len(treatment_numbers)} Treatments</div>', unsafe_allow_html=True)
                with col3:
                    if st.button("Select All"):
                        st.session_state.selected_treatments = treatment_numbers.copy()
                        st.session_state.show_analysis = False  # Prevent auto-processing
                        st.rerun()
                with col4:
                    if st.button("Deselect All"):
                        st.session_state.selected_treatments = []
                        st.session_state.show_analysis = False  # Prevent auto-processing
                        st.rerun()
            
            # Create columns for inline checkboxes
            num_cols = min(len(treatment_numbers), 8)
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
            
            # Update selections in session state without triggering analysis
            if st.session_state.selected_treatments != current_selections:
                st.session_state.selected_treatments = current_selections
                st.session_state.show_analysis = False  # Reset analysis state when selection changes
            
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
                    st.markdown("<div class='myUniqueId'><h2>Patient Information</h2></div>", unsafe_allow_html=True)
                    st.write(f"**Patient Name:** {analysis_data['patient_name']} | **Date of Birth:** {analysis_data['dob']} | **Sex:** {analysis_data['sex']}")
                    
                    # Add case history analysis if text was entered
                    if case_history.strip():
                        st.markdown('<div class="case-history-section">', unsafe_allow_html=True)
                        st.subheader("Case History Analysis")
                        with st.spinner('Analyzing case history...'):
                            history_analysis = analyze_case_history(case_history, analysis_data)
                            st.write(history_analysis)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Add a separator
                    st.markdown("---")
                    
                    # Session comparison
                    if len(filtered_treatments) > 1:
                        st.subheader("Session Comparison")
                        with st.spinner('Analyzing treatment sessions...'):
                            comparison = compare_sessions_openai(analysis_data)
                            st.write(comparison)
                    else:
                        st.write("Upload multiple sessions to see comparison")
                    
                    # Add a separator
                    st.markdown("---")
                    
                    # Create DataFrame but hide the table display
                    df = pd.DataFrame.from_dict(analysis_data['treatments'], orient='index')
                    if analysis_data['schedule']:
                        df['Date'] = df.index.map(lambda x: analysis_data['schedule'].get(x, ''))
                        cols = ['Date'] + [col for col in df.columns if col != 'Date']
                        df = df[cols]
                    
                    # Show comparison table (hidden but preserved in code)
                    if False:  # This condition makes the section never display but keeps the code
                        st.subheader("Treatment Overview")
                        st.dataframe(df)
                    
                    # Add Treatment Progress Charts section

                    st.subheader("Treatment Progress Charts")
                    
                    if len(analysis_data['treatments']) > 1:  # Only show charts for multiple sessions
                        # Create data for the phase duration chart
                        treatment_nums = []
                        hypoxic_durations = []
                        hyperoxic_durations = []
                        
                        for treatment_num, data in sorted(analysis_data['treatments'].items()):
                            treatment_nums.append(treatment_num)
                            
                            # Process hypoxic duration
                            hypo_str = data.get('Hypox. Phase dur. Av. (min:sec)', '0:00')
                            hypo_min, hypo_sec = map(int, hypo_str.split(':'))
                            hypoxic_durations.append(hypo_min + hypo_sec/60)
                            
                            # Process hyperoxic duration
                            hyper_str = data.get('Hyperox. Phase dur. Av. (min:sec)', '0:00')
                            hyper_min, hyper_sec = map(int, hyper_str.split(':'))
                            hyperoxic_durations.append(hyper_min + hyper_sec/60)
                        
                        # Create phase duration chart
                        st.write("**Phase Duration Analysis:**")
                        with st.spinner('Analyzing phase durations...'):
                            phase_analysis = analyze_phase_durations(analysis_data)
                        
                        # Create phase duration chart
                        fig = go.Figure()
                        
                        fig.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=hyperoxic_durations,
                            name='Hyperoxic Phase',
                            mode='lines+markers'
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=hypoxic_durations,
                            name='Hypoxic Phase',
                            mode='lines+markers'
                        ))
                        
                        fig.update_layout(
                            title='Hyperoxic/Hypoxic Phase Durations Across Sessions',
                            xaxis_title='Session Number',
                            yaxis_title='Duration (minutes)',
                            legend=dict(
                                orientation="v",
                                yanchor="middle",
                                y=0.5,
                                xanchor="left",
                                x=1.02,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=100, b=50),
                            height=500
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        st.write(phase_analysis)
                        
                        st.markdown("---")
                        
                        # Create data for the pulse rate chart
                        min_pr_avg = []
                        max_pr_avg = []
                        
                        for treatment_num, data in sorted(analysis_data['treatments'].items()):
                            # Process min PR average
                            min_pr_str = data.get('Min PR Av. (bpm)', '0')
                            min_pr_avg.append(float(min_pr_str.split()[0]))
                            
                            # Process max PR average
                            max_pr_str = data.get('Max PR Av. (bpm)', '0')
                            max_pr_avg.append(float(max_pr_str.split()[0]))
                        
                        # Create pulse rate chart
                        st.write("**Pulse Rate Analysis:**")
                        with st.spinner('Analyzing pulse rate trends...'):
                            pr_analysis = analyze_pr_trends(analysis_data)
                        
                        # Create pulse rate chart
                        fig_pr = go.Figure()
                        
                        fig_pr.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=max_pr_avg,
                            name='Max PR Average',
                            mode='lines+markers'
                        ))
                        
                        fig_pr.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=min_pr_avg,
                            name='Min PR Average',
                            mode='lines+markers'
                        ))
                        
                        fig_pr.update_layout(
                            title='Pulse Rate Average Across Sessions',
                            xaxis_title='Session Number',
                            yaxis_title='Pulse Rate (bpm)',
                            legend=dict(
                                orientation="v",
                                yanchor="middle",
                                y=0.5,
                                xanchor="left",
                                x=1.02,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=100, b=50),
                            height=500
                        )
                        
                        st.plotly_chart(fig_pr, use_container_width=True)
                        st.write(pr_analysis)
                        
                        st.markdown("---")
                        
                        # Create data for total hypoxic time chart
                        total_hypoxic_times = []
                        
                        for treatment_num, data in sorted(analysis_data['treatments'].items()):
                            try:
                                # Calculate total hypoxic time
                                hypoxic_dur = data.get('Hypox. Phase dur. Av. (min:sec)', '0:00')
                                hypo_min, hypo_sec = map(int, hypoxic_dur.split(':'))
                                total_seconds = hypo_min * 60 + hypo_sec
                                
                                cycles_str = data.get('Number of cycles', '0')
                                num_cycles = int(cycles_str.split()[0])
                                
                                total_minutes = (total_seconds * num_cycles) / 60
                                total_hypoxic_times.append(total_minutes)
                            except (ValueError, IndexError):
                                total_hypoxic_times.append(0)
                        
                        # Create total hypoxic time chart
                        st.write("**Total Hypoxic Time Analysis:**")
                        with st.spinner('Analyzing hypoxic time trends...'):
                            hypoxic_time_analysis = analyze_hypoxic_time(analysis_data)
                        
                        # Create total hypoxic time chart
                        fig_hypoxic = go.Figure()
                        
                        fig_hypoxic.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=total_hypoxic_times,
                            name='Total Hypoxic Time',
                            mode='lines+markers'
                        ))
                        
                        fig_hypoxic.update_layout(
                            title='Total Hypoxic Time Across Sessions',
                            xaxis_title='Session Number',
                            yaxis_title='Duration (minutes)',
                            legend=dict(
                                orientation="v",
                                yanchor="middle",
                                y=0.5,
                                xanchor="left",
                                x=1.02,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=100, b=50),
                            height=500
                        )
                        
                        st.plotly_chart(fig_hypoxic, use_container_width=True)
                        st.write(hypoxic_time_analysis)
                        
                        st.markdown("---")
                        
                        # Create data for blood pressure chart
                        bp_before = []
                        bp_after = []
                        
                        # Add the BP analysis section first
                        st.write("**Blood Pressure Analysis:**")
                        with st.spinner('Analyzing BP trends...'):
                            bp_analysis = analyze_bp_trends(analysis_data)
                        
                        for treatment_num, data in sorted(analysis_data['treatments'].items()):
                            # Convert BP values to display format
                            sys_before = data.get('BP SYS before (mmHg)', 'N/A')
                            dia_before = data.get('BP DIA before (mmHg)', 'N/A')
                            sys_after = data.get('BP SYS after (mmHg)', 'N/A')
                            dia_after = data.get('BP DIA after (mmHg)', 'N/A')
                            
                            # Format BP values - only append if both systolic and diastolic are valid numbers
                            try:
                                if sys_before != 'N/A' and dia_before != 'N/A':
                                    sys_before = float(sys_before)
                                    dia_before = float(dia_before)
                                    bp_before.append(sys_before)  # Only use systolic value for plotting
                                else:
                                    bp_before.append(None)
                                    
                                if sys_after != 'N/A' and dia_after != 'N/A':
                                    sys_after = float(sys_after)
                                    dia_after = float(dia_after)
                                    bp_after.append(sys_after)  # Only use systolic value for plotting
                                else:
                                    bp_after.append(None)
                            except (ValueError, TypeError):
                                bp_before.append(None)
                                bp_after.append(None)
                        
                        # BP Comparison Chart
                        fig_bp_comparison = go.Figure()
                        
                        fig_bp_comparison.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=bp_before,
                            name='BP Before Procedure',
                            mode='lines+markers',
                            connectgaps=True
                        ))
                        
                        fig_bp_comparison.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=bp_after,
                            name='BP After Procedure',
                            mode='lines+markers',
                            connectgaps=True
                        ))
                        
                        fig_bp_comparison.update_layout(
                            title='Blood Pressure Trends Across Sessions',
                            xaxis_title='Session Number',
                            yaxis_title='Blood Pressure (mmHg)',
                            legend=dict(
                                orientation="v",
                                yanchor="middle",
                                y=0.5,
                                xanchor="left",
                                x=1.02,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=100, b=50),
                            height=500
                        )
                        
                        st.plotly_chart(fig_bp_comparison, use_container_width=True)
                        st.write(bp_analysis)
                    else:
                        st.write("Upload multiple sessions to see progress charts")
                    
                    st.markdown("---")
                    
                    # Now add the Detailed Treatment Overview section
                    # Add custom CSS for styling
                    st.markdown("""
                        <style>
                            /* Style for the section header */
                            .detailed-overview-header {
                                font-size: 24px;
                                color: #1E88E5;
                                padding: 10px 0;
                                border-bottom: 2px solid #1E88E5;
                                margin-bottom: 20px;
                            }
                            
                            /* Style for tab labels */
                            .stTabs [data-baseweb="tab-list"] {
                                gap: 8px;
                            }
                            
                            .stTabs [data-baseweb="tab"] {
                                background-color: #f0f2f6;
                                border-radius: 4px;
                                padding: 8px 16px;
                                font-weight: 500;
                            }
                            
                            .stTabs [aria-selected="true"] {
                                background-color: #1E88E5;
                                color: white;
                            }
                            
                            /* Style for table headers and cells */
                            .treatment-header {
                                font-weight: bold;
                                color: #1E88E5;
                                font-size: 16px;
                                padding: 8px 0;
                                border-bottom: 1px solid #e0e0e0;
                            }
                            
                            .field-label {
                                font-weight: 500;
                                color: #424242;
                                background-color: #f5f5f5;
                                padding: 6px;
                                border-radius: 4px;
                                margin: 2px 0;
                            }
                            
                            .field-value {
                                padding: 6px;
                                border-radius: 4px;
                                background-color: white;
                                margin: 2px 0;
                                border: 1px solid #e0e0e0;
                            }
                            
                            /* Keep Case History Analysis heading with content */
                            h2:contains("Case History Analysis") {
                                break-inside: avoid !important;
                                page-break-inside: avoid !important;
                            }
                            
                            /* Keep the analysis text with its heading */
                            h2:contains("Case History Analysis") + p {
                                break-inside: avoid !important;
                                page-break-inside: avoid !important;
                            }
                            
                            /* Create a wrapper for the heading and content */
                            .case-history-section {
                                break-inside: avoid !important;
                                page-break-inside: avoid !important;
                                margin-bottom: 20px !important;
                            }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    # Add paginated detailed view with styled header
                    st.markdown('<h2 class="detailed-overview-header">Detailed Treatment Overview</h2>', unsafe_allow_html=True)
                    if analysis_data['treatments']:
                        st.markdown('<div class="detailed-overview-content">', unsafe_allow_html=True)
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
                            ('total_hypoxic_calc', 'Total Hypoxic Time (approx)'),
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
                                cols = st.columns(len(current_treatments) + 1)
                                
                                # Treatment number headers
                                for i, (treatment_num, _) in enumerate(current_treatments, 1):
                                    cols[i].markdown(f'<div class="treatment-header">Session {treatment_num}</div>', unsafe_allow_html=True)
                                
                                # Create rows
                                for field_key, field_label in fields:
                                    cols = st.columns(len(current_treatments) + 1)
                                    cols[0].markdown(f'<div class="field-label">{field_label}</div>', unsafe_allow_html=True)
                                    for i, (treatment_num, data) in enumerate(current_treatments, 1):
                                        if field_key == 'BP_before':
                                            sys_before = data.get('BP SYS before (mmHg)', 'N/A')
                                            dia_before = data.get('BP DIA before (mmHg)', 'N/A')
                                            value = f"{sys_before}/{dia_before}" if sys_before != 'N/A' else 'N/A'
                                        elif field_key == 'BP_after':
                                            sys_after = data.get('BP SYS after (mmHg)', 'N/A')
                                            dia_after = data.get('BP DIA after (mmHg)', 'N/A')
                                            value = f"{sys_after}/{dia_after}" if sys_after != 'N/A' else 'N/A'
                                        elif field_key == 'total_hypoxic_calc':
                                            try:
                                                # Get hypoxic phase duration
                                                hypoxic_dur = data.get('Hypox. Phase dur. Av. (min:sec)', 'N/A')
                                                if hypoxic_dur != 'N/A':
                                                    # Convert "MM:SS" to total seconds
                                                    min_sec = hypoxic_dur.split(':')
                                                    total_seconds = int(min_sec[0]) * 60 + int(min_sec[1])
                                                    
                                                    # Get number of cycles
                                                    cycles_str = data.get('Number of cycles', 'N/A')
                                                    if cycles_str != 'N/A':
                                                        num_cycles = int(cycles_str.split()[0])  # Get first number
                                                        
                                                        # Calculate total time in seconds
                                                        total_time_seconds = total_seconds * num_cycles
                                                        
                                                        # Convert back to MM:SS format
                                                        minutes = total_time_seconds // 60
                                                        seconds = total_time_seconds % 60
                                                        value = f"{minutes:02d}:{seconds:02d}"
                                                    else:
                                                        value = 'N/A'
                                                else:
                                                    value = 'N/A'
                                            except (ValueError, IndexError):
                                                value = 'N/A'
                                        else:
                                            value = df.loc[treatment_num, field_key] if field_key in df.columns else data.get(field_key, 'N/A')
                                        cols[i].markdown(f'<div class="field-value">{value}</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main() 