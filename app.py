import streamlit as st
import pdfplumber
import io
from collections import OrderedDict
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px
from anthropic import Anthropic
import anthropic

# Load environment variables
load_dotenv()

def extract_text_from_pdf(pdf_file):
    try:
        # Reset file pointer to the beginning
        pdf_file.seek(0)
        
        pdf_bytes = pdf_file.read()
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        
        # Dictionary to store patient data
        patient_data = {
            # Existing fields
            'patient_name': '',
            'reference_number': '',
            'sex': '',
            'date_of_birth': '',
            'treatment_number': '',
            'treatment_date': '',
            
            # Results section
            'total_duration': '',
            'total_hypoxic_time': '',
            'adjustment_time': '',
            'number_of_hypoxic_phases': '',
            'hypoxic_phase_duration_avg': '',
            'min_spo2_average': '',
            'number_of_hyperoxic_phases': '',
            'hyperoxic_phase_duration_avg': '',
            'max_spo2_average': '',
            'baseline_pr': '',
            'min_pr_average': '',
            'max_pr_average': '',
            'pr_after_procedure': '',
            'pr_elevation_bpm': '',
            'pr_elevation_percent': ''
        }
        
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=True,
                use_text_flow=True
            )
            
            word_list = [w['text'].strip() for w in words]

            
            
            # Process Results section
            for i, word in enumerate(word_list):
                # Patient info (using exact indices we can see)
                if word == "Patient name":
                    patient_data['patient_name'] = word_list[2]  # Index 2
                elif word == "Ref. No.":
                    patient_data['reference_number'] = word_list[3]  # Index 3
                elif word == "Sex":
                    patient_data['sex'] = word_list[8]  # Index 8
                elif word == "Date of birth":
                    patient_data['date_of_birth'] = word_list[9]  # Index 9
                elif word == "Treatment No.":
                    patient_data['treatment_number'] = word_list[10]  # Index 10
                elif word == "Date" and i > 6:  # Treatment date
                    patient_data['treatment_date'] = word_list[11]  # Index 11
                
                # Results section (using exact indices)
                elif word == "Total duration":
                    patient_data['total_duration'] = word_list[39]  # "41:09 min:sec"
                elif word == "Total hypoxic time":
                    patient_data['total_hypoxic_time'] = word_list[40]  # "16:40 min:sec"
                elif word == "Adjustment time":
                    patient_data['adjustment_time'] = word_list[41]  # "08:36 min:sec"
                elif word == "Number of hypoxic phases":
                    patient_data['number_of_hypoxic_phases'] = word_list[46]  # "5"
                elif word == "Hypoxic phase duration average":
                    patient_data['hypoxic_phase_duration_avg'] = word_list[47]  # "03:20 min:sec"
                elif word == "Min SpO":
                    patient_data['min_spo2_average'] = word_list[48]  # "82 %"
                elif word == "Number of hyperoxic phases":
                    patient_data['number_of_hyperoxic_phases'] = word_list[53]  # "5"
                elif word == "Hyperoxic phase duration average":
                    patient_data['hyperoxic_phase_duration_avg'] = word_list[54]  # "03:52 min:sec"
                elif word == "Max SpO":
                    patient_data['max_spo2_average'] = word_list[55]  # "100 %"
                elif word == "Baseline PR":
                    patient_data['baseline_pr'] = word_list[59]  # "71 bpm"
                elif word == "Min PR average":
                    patient_data['min_pr_average'] = word_list[60]  # "58 bpm"
                elif word == "Max PR average":
                    patient_data['max_pr_average'] = word_list[61]  # "84 bpm"
                elif word == "PR after procedure":
                    patient_data['pr_after_procedure'] = word_list[65]  # "69 bpm"
                elif word == "PR elevation (BPM)":
                    patient_data['pr_elevation_bpm'] = word_list[66]  # "13,00"
                elif word == "PR elevation (%)":
                    patient_data['pr_elevation_percent'] = word_list[67]  # "18,31"
        
        pdf.close()
        
        # Format output
        formatted_output = [
            f"Patient Name: {patient_data['patient_name']}",
            f"Reference Number: {patient_data['reference_number']}",
            f"Sex: {patient_data['sex']}",
            f"Date of Birth: {patient_data['date_of_birth']}",
            f"Treatment Number: {patient_data['treatment_number']}",
            f"Treatment Date: {patient_data['treatment_date']}",
            
            "\nResults:",
            f"Total Duration: {patient_data['total_duration']}",
            f"Total Hypoxic Time: {patient_data['total_hypoxic_time']}",
            f"Adjustment Time: {patient_data['adjustment_time']}",
            f"Number of Hypoxic Phases: {patient_data['number_of_hypoxic_phases']}",
            f"Hypoxic Phase Duration Average: {patient_data['hypoxic_phase_duration_avg']}",
            f"Min SpO2 Average: {patient_data['min_spo2_average']}",
            f"Number of Hyperoxic Phases: {patient_data['number_of_hyperoxic_phases']}",
            f"Hyperoxic Phase Duration Average: {patient_data['hyperoxic_phase_duration_avg']}",
            f"Max SpO2 Average: {patient_data['max_spo2_average']}",
            f"Baseline PR: {patient_data['baseline_pr']}",
            f"Min PR Average: {patient_data['min_pr_average']}",
            f"Max PR Average: {patient_data['max_pr_average']}",
            f"PR After Procedure: {patient_data['pr_after_procedure']}",
            f"PR Elevation (BPM): {patient_data['pr_elevation_bpm']}",
            f"PR Elevation (%): {patient_data['pr_elevation_percent']}"
        ]
        
        return formatted_output, patient_data
        
    except Exception as e:
        st.error(f"Error in extract_text_from_pdf: {str(e)}")
        st.write("Full error:", str(e))
        return [], {}

def compare_sessions_openai(sorted_results):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            sessions_data.append(f"""
            Session {treatment_num}:
            Adaptive Response Metrics:
            - PR Elevation: {data['pr_elevation_percent']}%
            - Baseline PR: {data['baseline_pr']}
            - PR After Treatment: {data['pr_after_procedure']}
            - Min SpO2: {data['min_spo2_average']}
            - Max SpO2: {data['max_spo2_average']}
            - Total Hypoxic Time: {data['total_hypoxic_time']}
            """)
        
        prompt = f"""Analyze the adaptive response changes between these ReOxy sessions. Focus on:
        1. Heart rate adaptation trends
        2. SpO2 tolerance improvements
        3. Changes in hypoxic exposure tolerance
        
        Sessions:{''.join(sessions_data)}
        
        Highlight key improvements in physiological adaptation between sessions."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def compare_sessions_claude(sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            sessions_data.append(f"""
            Session {treatment_num}:
            Adaptive Response Metrics:
            - PR Elevation: {data['pr_elevation_percent']}%
            - Baseline PR: {data['baseline_pr']}
            - PR After Treatment: {data['pr_after_procedure']}
            - Min SpO2: {data['min_spo2_average']}
            - Max SpO2: {data['max_spo2_average']}
            - Total Hypoxic Time: {data['total_hypoxic_time']}
            """)
        
        prompt = f"""Analyze the adaptive response across these ReOxy treatment sessions:

        1. Compare heart rate adaptations:
           - Changes in baseline PR between sessions
           - PR elevation trends
           - Post-treatment PR recovery patterns
        
        2. Analyze SpO2 adaptation:
           - Changes in minimum SpO2 tolerance
           - Adaptation to hypoxic exposure time
           - Overall adaptation to hypoxic stress
        
        3. Highlight any improvements or changes in adaptive capacity between sessions.

        Sessions:{''.join(sessions_data)}
        
        Please focus on physiological adaptations and improvements in tolerance to hypoxic stress."""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def generate_recommendations(patient_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"""
        Based on this ReOxy treatment data:
        - Min SpO2: {patient_data['min_spo2_average']}
        - Max SpO2: {patient_data['max_spo2_average']}
        - PR Elevation: {patient_data['pr_elevation_percent']}%
        
        Provide recommendations for future treatments.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def generate_recommendations_claude(patient_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = f"""
        Based on this ReOxy treatment data, provide specific recommendations for future treatments:
        
        Patient Data:
        - Total Duration: {patient_data['total_duration']}
        - Total Hypoxic Time: {patient_data['total_hypoxic_time']}
        - Min SpO2 Average: {patient_data['min_spo2_average']}
        - Max SpO2 Average: {patient_data['max_spo2_average']}
        - PR Elevation: {patient_data['pr_elevation_percent']}%
        - Baseline PR: {patient_data['baseline_pr']}
        - PR After: {patient_data['pr_after_procedure']}
        
        Please provide:
        1. Specific adjustments for future sessions
        2. Safety considerations based on the data
        3. Potential areas for improvement
        """
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def create_charts(sorted_results):
    treatment_numbers = list(sorted_results.keys())
    
    # Calculate PR Average and get PR after procedure and baseline
    pr_averages = []
    pr_after = []
    pr_baseline = []
    
    for data in sorted_results.values():
        # Calculate average of Min and Max PR
        min_pr = float(data['min_pr_average'].split(' ')[0])
        max_pr = float(data['max_pr_average'].split(' ')[0])
        pr_avg = (min_pr + max_pr) / 2
        pr_averages.append(pr_avg)
        
        # Get PR after procedure and baseline
        pr_after.append(float(data['pr_after_procedure'].split(' ')[0]))
        pr_baseline.append(float(data['baseline_pr'].split(' ')[0]))
    
    # PR Comparison Chart
    fig_pr_comparison = go.Figure()
    fig_pr_comparison.add_trace(go.Scatter(
        x=treatment_numbers,
        y=pr_baseline,
        name='Baseline PR',
        mode='lines+markers'
    ))
    fig_pr_comparison.add_trace(go.Scatter(
        x=treatment_numbers,
        y=pr_averages,
        name='PR Average',
        mode='lines+markers'
    ))
    fig_pr_comparison.add_trace(go.Scatter(
        x=treatment_numbers,
        y=pr_after,
        name='PR After Procedure',
        mode='lines+markers'
    ))
    fig_pr_comparison.update_layout(
        title='Pulse Rate Trends Across Sessions',
        xaxis_title='Session Number',
        yaxis_title='Pulse Rate (bpm)'
    )
    
    # Process both hyperoxic and hypoxic duration data
    hyperoxic_durations = []
    hypoxic_durations = []
    
    for data in sorted_results.values():
        # Process hyperoxic duration
        hyper_str = data['hyperoxic_phase_duration_avg'].split(' ')[0]
        hyper_min, hyper_sec = map(int, hyper_str.split(':'))
        hyperoxic_durations.append(hyper_min + hyper_sec/60)
        
        # Process hypoxic duration
        hypo_str = data['hypoxic_phase_duration_avg'].split(' ')[0]
        hypo_min, hypo_sec = map(int, hypo_str.split(':'))
        hypoxic_durations.append(hypo_min + hypo_sec/60)
    
    # Combined Phase Duration Chart
    fig_phases = go.Figure()
    fig_phases.add_trace(go.Scatter(
        x=treatment_numbers, 
        y=hyperoxic_durations, 
        name='Hyperoxic Phase',
        mode='lines+markers'
    ))
    fig_phases.add_trace(go.Scatter(
        x=treatment_numbers, 
        y=hypoxic_durations, 
        name='Hypoxic Phase',
        mode='lines+markers'
    ))
    fig_phases.update_layout(
        title='Hyperoxic/Hypoxic Phase Durations Across Sessions',
        xaxis_title='Session Number',
        yaxis_title='Duration (minutes)'
    )
    
    # Total Hypoxic Time Chart
    hypoxic_times = []
    for data in sorted_results.values():
        time_str = data['total_hypoxic_time'].split(' ')[0]  # Get "MM:SS" part
        minutes, seconds = map(int, time_str.split(':'))
        total_minutes = minutes + seconds/60
        hypoxic_times.append(total_minutes)
    
    fig_hypoxic_time = go.Figure()
    fig_hypoxic_time.add_trace(go.Scatter(
        x=treatment_numbers,
        y=hypoxic_times,
        mode='lines+markers'
    ))
    fig_hypoxic_time.update_layout(
        title='Total Hypoxic Time Across Sessions',
        xaxis_title='Session Number',
        yaxis_title='Duration (minutes)'
    )
    
    return fig_pr_comparison, fig_phases, fig_hypoxic_time

def analyze_hyperoxic_duration(sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            sessions_data.append(f"""
            Session {treatment_num}:
            - Hyperoxic Phase Duration: {data['hyperoxic_phase_duration_avg']}
            - Hypoxic Phase Duration: {data['hypoxic_phase_duration_avg']}
            - PR Elevation: {data['pr_elevation_percent']}%
            - SpO2 Max: {data['max_spo2_average']}
            - SpO2 Min: {data['min_spo2_average']}
            """)
        
        prompt = f"""Analyze the hyperoxic and hypoxic phase duration trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between hyperoxic and hypoxic durations
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing phase durations: {str(e)}"

def analyze_pr_trends(sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            min_pr = float(data['min_pr_average'].split(' ')[0])
            max_pr = float(data['max_pr_average'].split(' ')[0])
            pr_avg = (min_pr + max_pr) / 2
            
            sessions_data.append(f"""
            Session {treatment_num}:
            - PR Average: {pr_avg:.1f} bpm
            - PR After Procedure: {data['pr_after_procedure']}
            - PR Elevation: {data['pr_elevation_percent']}%
            """)
        
        prompt = f"""Analyze the relationship between PR Average (mean of Min and Max PR) and PR After Procedure across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The recovery pattern shown by PR After Procedure compared to PR Average
        2. What this indicates about the patient's cardiovascular adaptation to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing PR trends: {str(e)}"

def analyze_hypoxic_time(sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            sessions_data.append(f"""
            Session {treatment_num}:
            - Total Hypoxic Time: {data['total_hypoxic_time']}
            - PR Elevation: {data['pr_elevation_percent']}%
            - Min SpO2: {data['min_spo2_average']}
            """)
        
        prompt = f"""Analyze the total hypoxic time trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. Changes in hypoxic exposure duration
        2. What this suggests about the patient's adaptation to hypoxic stress

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing hypoxic time: {str(e)}"

def main():
    st.set_page_config(layout="wide")
    
    st.title("ReOxy Reports Interpreter")
        
    # Changed order to make Claude the default
    ai_model = st.sidebar.selectbox(
        "Select AI Model",
        ["Claude 3 Sonnet", "OpenAI GPT-3.5"]
    )
    
    # Initialize session state for uploaded files
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    # File uploader
    new_files = st.file_uploader(
        "Choose PDF files", 
        type="pdf", 
        accept_multiple_files=True,
        key='pdf_uploader'
    )
    
    # Only show clear button if there are files uploaded
    if new_files:
        # Show loading overlay while processing files
        with st.spinner('Processing PDF files... Please wait.'):
            st.session_state.uploaded_files = []
            
            # First, validate all files have the same patient name
            patient_names = set()
            valid_files = []
            
            def is_valid_reoxy_report(patient_data):
                # Define required fields that should be present in a ReOxy report
                required_fields = [
                    'total_duration',
                    'total_hypoxic_time',
                    'number_of_hypoxic_phases',
                    'min_spo2_average',
                    'number_of_hyperoxic_phases',
                    'max_spo2_average',
                    'baseline_pr',
                    'pr_elevation_percent'
                ]
                
                # Check if all required fields exist and have non-empty values
                for field in required_fields:
                    if field not in patient_data or not patient_data[field]:
                        return False
                return True
            
            for file in new_files:
                file_copy = io.BytesIO(file.read())
                file_copy.name = file.name
                file.seek(0)
                
                try:
                    # Extract data and validate
                    formatted_text, patient_data = extract_text_from_pdf(file_copy)
                    
                    # Check if it's a valid ReOxy report
                    if not is_valid_reoxy_report(patient_data):
                        st.error(f"Error: {file.name} does not appear to be a valid ReOxy report. Please upload only ReOxy PDF reports. ReLoad the page")
                        continue
                    
                    patient_names.add(patient_data['patient_name'])
                    valid_files.append(file_copy)
                except Exception as e:
                    st.error(f"Error processing {file.name}: {str(e)}")
            
            # Check if all files are for the same patient
            if len(patient_names) > 1:
                st.error("Error: Multiple patient names detected. Please upload files for the same patient only. ReLoad the page")
                return
            elif len(patient_names) == 0:
                st.error("Error: No valid ReOxy reports found in uploaded files.")
                return
            
            # If validation passes, proceed with processing
            st.session_state.uploaded_files = valid_files
            
            # Process uploaded files and extract data
            all_results = {}
            first_patient = None
            
            for uploaded_file in st.session_state.uploaded_files:
                try:
                    formatted_text, patient_data = extract_text_from_pdf(uploaded_file)
                    treatment_num = int(patient_data['treatment_number'])
                    all_results[treatment_num] = patient_data
                    
                    # Store the first patient's data
                    if first_patient is None:
                        first_patient = patient_data
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {str(e)}")
            
            # Sort results by treatment number
            sorted_results = OrderedDict(sorted(all_results.items()))

            # After processing files and before displaying the table
            if sorted_results:
                # Display Patient Information first
                st.subheader("Patient Information")
                first_patient = next(iter(sorted_results.values()))
                st.write(f"**Patient Name:** {first_patient['patient_name']}")
                st.write(f"**Date of Birth:** {first_patient['date_of_birth']}")
                st.write(f"**Sex:** {first_patient['sex']}")
                
                # Add a separator
                st.markdown("---")
                
                # Keep two columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Session Comparison")
                    if len(sorted_results) > 1:
                        comparison = compare_sessions_claude(sorted_results) if ai_model == "Claude 3 Sonnet" else compare_sessions_openai(sorted_results)
                        st.write(comparison)
                    else:
                        st.write("Upload multiple sessions to see comparison")
                
                with col2:
                    st.subheader("Treatment Recommendations")
                    latest_session = sorted_results[max(sorted_results.keys())]
                    recommendations = generate_recommendations_claude(latest_session) if ai_model == "Claude 3 Sonnet" else generate_recommendations(latest_session)
                    st.write(recommendations)
                
                # Add a separator before the table
                st.markdown("---")
                
                  # Add charts section
 
                st.subheader("Treatment Progress Charts")
                
                if len(sorted_results) > 1:  # Only show charts if there are multiple sessions
                    fig_pr_comparison, fig_phases, fig_hypoxic_time = create_charts(sorted_results)
                    
                    # Display phase duration chart and analysis
                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        st.plotly_chart(fig_phases, use_container_width=True, key="phase_duration_chart")
                    with chart_col2:
                        st.write("**Phase Duration Analysis:**")
                        phase_analysis = analyze_hyperoxic_duration(sorted_results)
                        st.write(phase_analysis)
                    
                    # Display PR comparison and analysis
                    pr_col1, pr_col2 = st.columns(2)
                    with pr_col1:
                        st.plotly_chart(fig_pr_comparison, use_container_width=True, key="pr_comparison_chart")
                    with pr_col2:
                        st.write("**Pulse Rate Analysis:**")
                        pr_analysis = analyze_pr_trends(sorted_results)
                        st.write(pr_analysis)
                    
                    # Display Total Hypoxic Time chart and analysis
                    hypoxic_col1, hypoxic_col2 = st.columns(2)
                    with hypoxic_col1:
                        st.plotly_chart(fig_hypoxic_time, use_container_width=True, key="hypoxic_time_chart")
                    with hypoxic_col2:
                        st.write("**Total Hypoxic Time Analysis:**")
                        hypoxic_analysis = analyze_hypoxic_time(sorted_results)
                        st.write(hypoxic_analysis)
                    
                    # Add a separator before the extracted results
                    st.markdown("---")
                    
                    # Display extracted results in an expander
                    with st.expander("Extracted Results", expanded=False):
                        # Create a table header
                        cols = st.columns(len(sorted_results) + 1)  # +1 for labels column
                        
                        # Labels column
                        for i, (treatment_num, data) in enumerate(sorted_results.items(), 1):
                            cols[i].write(f"Session {treatment_num}")
                        
                        # Data rows
                        fields = [
                            ('treatment_date', 'Treatment Date'),
                            ('total_duration', 'Total Duration'),
                            ('total_hypoxic_time', 'Total Hypoxic Time'),
                            ('adjustment_time', 'Adjustment Time'),
                            ('number_of_hypoxic_phases', 'Number of Hypoxic Phases'),
                            ('hypoxic_phase_duration_avg', 'Hypoxic Phase Duration Average'),
                            ('min_spo2_average', 'Min SpO2 Average'),
                            ('number_of_hyperoxic_phases', 'Number of Hyperoxic Phases'),
                            ('hyperoxic_phase_duration_avg', 'Hyperoxic Phase Duration Average'),
                            ('max_spo2_average', 'Max SpO2 Average'),
                            ('baseline_pr', 'Baseline PR'),
                            ('min_pr_average', 'Min PR Average'),
                            ('max_pr_average', 'Max PR Average'),
                            ('pr_after_procedure', 'PR After Procedure'),
                            ('pr_elevation_bpm', 'PR Elevation (BPM)'),
                            ('pr_elevation_percent', 'PR Elevation (%)')
                        ]
                        
                        # Create rows
                        for field_key, field_label in fields:
                            cols = st.columns(len(sorted_results) + 1)
                            cols[0].write(field_label)
                            for i, data in enumerate(sorted_results.values(), 1):
                                cols[i].write(data[field_key])
                else:
                    st.write("Upload multiple sessions to see progress charts")

                # Add download button for CSV
                # Convert to DataFrame
                df = pd.DataFrame.from_dict(sorted_results, orient='index')
                
                # Create CSV
                csv = df.to_csv(index=True)
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name="treatment_results.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main() 