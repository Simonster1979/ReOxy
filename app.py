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
from export_pdf_utils import *
# Load environment variables
load_dotenv()
content_to_export = []
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
            'pr_elevation_percent': '',
            
            # Add new fields for blood pressure
            'bp_before_procedure': '',
            'bp_after_procedure': '',
        }
        
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=6,
                y_tolerance=2,
                keep_blank_chars=True,
                use_text_flow=True
            )
            
            # word_list = [w['text'].strip() for w in words]
            word_list = [word for word in word_list if word != '2']

            print("<----------- --------- ------------- ----------->")
            print(word_list)  # or st.write(word_list)
            print("<---------------------->")
            
            
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
                
                # Add extraction for BP before and after procedure
                elif word == "BP before procedure":
                    patient_data['bp_before_procedure'] = word_list[71]  # Adjust index as needed
                elif word == "BP after procedure":
                    patient_data['bp_after_procedure'] = word_list[72]  # Adjust index as needed
        
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
            f"PR Elevation (%): {patient_data['pr_elevation_percent']}",
            f"BP Before Procedure: {patient_data['bp_before_procedure']}",
            f"BP After Procedure: {patient_data['bp_after_procedure']}"
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
            # Convert BP values to display format
            bp_before = 'N/A' if data['bp_before_procedure'] == '---' else data['bp_before_procedure']
            bp_after = 'N/A' if data['bp_after_procedure'] == '---' else data['bp_after_procedure']
            
            sessions_data.append(f"""
            Session {treatment_num}:
            Adaptive Response Metrics:
            - PR Elevation: {data['pr_elevation_percent']}%
            - Baseline PR: {data['baseline_pr']}
            - PR After Treatment: {data['pr_after_procedure']}
            - Min SpO2: {data['min_spo2_average']}
            - Max SpO2: {data['max_spo2_average']}
            - Total Hypoxic Time: {data['total_hypoxic_time']}
            Blood Pressure Response:
            - BP Before: {bp_before}
            - BP After: {bp_after}
            """)
        
        prompt = f"""Analyze the adaptive response changes between these ReOxy sessions. Focus on:
        1. Heart rate adaptation trends
        2. SpO2 tolerance improvements
        3. Changes in hypoxic exposure tolerance
        4. Blood pressure response patterns
        
        Sessions:{''.join(sessions_data)}
        
        Highlight key improvements in physiological adaptation between sessions, including cardiovascular responses shown by both heart rate and blood pressure changes.
        Return the results in markdown format and make sure to properly create unordered list items."""
        
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
        print(data)
        data["max_pr_average"].replace("Baseline Pr", "0")
        data["min_pr_average"].replace("Baseline Pr", "0")
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
        yaxis_title='Pulse Rate (bpm)',
        legend=dict(
            orientation="h",  # horizontal orientation
            yanchor="bottom",
            y=-0.3,  # position below chart
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        )
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
        yaxis_title='Duration (minutes)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        )
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
        yaxis_title='Duration (minutes)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        )
    )
    
    # New lists for BP values
    bp_before = []
    bp_after = []
    
    for data in sorted_results.values():
        bp_before.append(data['bp_before_procedure'])
        bp_after.append(data['bp_after_procedure'])
    
    # Convert BP values to numeric, handling various invalid values
    def convert_bp(bp_str):
        if bp_str in ["N/A", "---", "", None]:
            return None
        try:
            return float(bp_str.split(' ')[0])
        except (ValueError, AttributeError, IndexError):
            return None
    
    bp_before_numeric = [convert_bp(bp) for bp in bp_before]
    bp_after_numeric = [convert_bp(bp) for bp in bp_after]
    
    # BP Comparison Chart
    fig_bp_comparison = go.Figure()
    fig_bp_comparison.add_trace(go.Scatter(
        x=treatment_numbers,
        y=bp_before_numeric,
        name='BP Before Procedure',
        mode='lines+markers',
        connectgaps=True  # This will connect lines across missing values
    ))
    fig_bp_comparison.add_trace(go.Scatter(
        x=treatment_numbers,
        y=bp_after_numeric,
        name='BP After Procedure',
        mode='lines+markers',
        connectgaps=True
    ))
    fig_bp_comparison.update_layout(
        title='Blood Pressure Trends Across Sessions',
        xaxis_title='Session Number',
        yaxis_title='Blood Pressure (mmHg)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        )
    )
    
    # Add margin to all charts to accommodate legend
    for fig in [fig_pr_comparison, fig_phases, fig_hypoxic_time, fig_bp_comparison]:
        fig.update_layout(
            margin=dict(t=50, l=50, r=50, b=100),  # increase bottom margin
            height=500  # adjust height to accommodate legend
        )
    
    return fig_pr_comparison, fig_phases, fig_hypoxic_time, fig_bp_comparison

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

def analyze_case_history(case_history, sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Get the latest session data
        latest_session = sorted_results[max(sorted_results.keys())]
        
        prompt = f"""Based on the patient's case history and ReOxy treatment results, identify key correlations and relevant clinical insights in 2-3 sentences.

        Case History:
        {case_history}

        Treatment Data:
        - Sessions: {len(sorted_results)}
        - Latest PR Elevation: {latest_session['pr_elevation_percent']}%
        - Latest SpO2 Range: {latest_session['min_spo2_average']} - {latest_session['max_spo2_average']}
        """
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,  # Reduced token limit for more concise response
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing case history: {str(e)}"

def analyze_bp_trends(sorted_results):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            # Only include BP data if it's valid
            if data['bp_before_procedure'] not in ["N/A", "---", ""]:
                sessions_data.append(f"""
                Session {treatment_num}:
                - BP Before: {data['bp_before_procedure']}
                - BP After: {data['bp_after_procedure']}
                - PR Elevation: {data['pr_elevation_percent']}%
                - Total Hypoxic Time: {data['total_hypoxic_time']}
                """)
        
        if not sessions_data:
            return "Insufficient blood pressure data available for analysis."
        
        prompt = f"""Analyze the blood pressure response across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The acute BP response to each session (before vs after)
        2. The overall trend across sessions and what this suggests about cardiovascular adaptation

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing BP trends: {str(e)}"

def main():
    # Custom CSS for print styling
    st.markdown("""
        <style>
            @media print {
                /* Keep charts together */
                .element-container {
                    break-inside: avoid !important;
                }
                
                .esjhkag0 {
                    display: none !important;
                }

                /* Ensure charts fit within page */
                .js-plotly-plot, .plotly {
                    max-height: 400px !important;
                    margin-bottom: 20px !important;
                    break-inside: avoid !important;
                }
                
                /* Keep text with charts */
                .stMarkdown {
                    break-inside: avoid !important;
                }
                
                /* Adjust margins and paper size */
                @page {
                    size: A4;
                    margin: 0.5cm;
                }
                
                /* Hide Streamlit components during print */
                .stButton, .stDownloadButton, header, footer {
                    display: none !important;
                }
                
                /* Hide file uploader components */
                .stFileUploader, [data-testid="stFileUploader"] {
                    display: none !important;
                }
                
                /* Hide the file list */
                [data-testid="stFileUploadDropzone"] {
                    display: none !important;
                }
                
                /* Hide pagination */
                .css-1p1nwyz {
                    display: none !important;
                }

                /* Hide sidebar */
                [data-testid="stSidebar"] {
                    display: none !important;
                }
                
                section[data-testid="stSidebarContent"] {
                    display: none !important;
                }
                
                .css-1d391kg {
                    display: none !important;
                }
                
                /* Hide Extracted Results section */
                [data-testid="stExpander"] {
                    display: none !important;
                }
                
                .streamlit-expanderHeader {
                    display: none !important;
                }
                
                /* Hide the download button */
                .stDownloadButton {
                    display: none !important;
                }
                
                /* Hide Detailed Treatment Overview section */
                .detailed-overview-header,
                .detailed-overview-content {
                    display: none !important;
                }
                
                /* Increase font sizes for print */
                h1 {
                    font-size: 32pt !important;
                }
                
                h2, h3, .stSubheader {
                    font-size: 26pt !important;
                }
                
                p, div, span, li {
                    font-size: 20pt !important;
                }
                
                /* Make analysis text larger */
                .stMarkdown p {
                    font-size: 20pt !important;
                    line-height: 1.4 !important;
                }
                
                /* Make chart titles and labels larger */
                .js-plotly-plot .plotly text {
                    font-size: 14pt !important;
                }
                
                /* Make table text larger */
                .element-container div {
                    font-size: 14pt !important;
                }
                
                /* Bold headers and labels */
                strong, b {
                    font-size: 22pt !important;
                    font-weight: bold !important;
                }
                
                /* Increase spacing between sections */
                .element-container {
                    margin-bottom: 20px !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("ReOxy Reports Interpreter")
    
    # Add case history text area
    case_history = st.text_area(
        "Patient Case History",
        height=150,
        help="Enter relevant patient history, conditions, medications, and other clinical notes",
        key="reoxy_case_history"
    )
    
    # Add a separator
    st.markdown("---")
    
    # Replace the selectbox with a default value
    ai_model = "OpenAI GPT-3.5"  # Changed from "Claude 3 Sonnet"

    # Add this CSS to hide any remaining selectbox
    st.markdown("""
        <style>
            /* Hide "Select AI Model" section */
            [data-testid="stSidebarSelectbox"] {
                display: none;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state for uploaded files
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    # File uploader
    new_files = st.file_uploader(
        "Choose PDF files", 
        type="pdf", 
        accept_multiple_files=True,
        key='reoxy_pdf_uploader'
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
                
                # Display patient information in a single line separated by '|'
                st.write(f"**Patient Name:** {first_patient['patient_name']} | **Date of Birth:** {first_patient['date_of_birth']} | **Sex:** {first_patient['sex']}")
                patient_details = AnalysisContent()
                patient_details.heading = "Patient Information"
                patient_details.paragraph = f"**Patient Name:** {first_patient['patient_name']} | **Date of Birth:** {first_patient['date_of_birth']} | **Sex:** {first_patient['sex']}"
                content_to_export.append(patient_details)
                # Add case history analysis if text was entered
                if case_history.strip():
                    st.subheader("Case History Analysis")
                    history_analysis = analyze_case_history(case_history, sorted_results)

                    case_history_analysis = AnalysisContent()
                    case_history_analysis.heading = "Case History Analysis"
                    case_history_analysis.paragraph = history_analysis
                    content_to_export.append(case_history_analysis)
                    st.write(history_analysis)
                
                # Add a separator
                st.markdown("---")
                
                # Session Comparison
                st.subheader("Session Comparison")
                if len(sorted_results) > 1:
                    comparison = compare_sessions_openai(sorted_results)
                    session_analysis_content = AnalysisContent()
                    session_analysis_content.sub_heading = "Session Comparison"
                    session_analysis_content.paragraph = comparison
                    st.write(comparison)
                else:
                    st.write("Upload multiple sessions to see comparison")
                
                # Add a separator before the charts section
                st.markdown("---")
                
                # Add charts section
                st.subheader("Treatment Progress Charts")
                
                if len(sorted_results) > 1:  # Only show charts for multiple sessions
                    # Create all charts first
                    fig_pr_comparison, fig_phases, fig_hypoxic_time, fig_bp_comparison = create_charts(sorted_results)
                    
                    # Phase Duration Chart
                    st.write("**Phase Duration Analysis:**")
                    st.plotly_chart(fig_phases, use_container_width=True)
                    with st.spinner('Analyzing phase durations...'):
                        phase_analysis = analyze_hyperoxic_duration(sorted_results)
                        analysis_content = AnalysisContent()
                        analysis_content.heading = "Treatment Progress Charts"
                        analysis_content.sub_heading = "Phase Duration Analysis"
                        analysis_content.paragraph = phase_analysis
                        analysis_content.figure = fig_phases
                        content_to_export.append(analysis_content)
                        st.write(phase_analysis)
                    
                    st.markdown("---")
                    
                    # PR Comparison Chart
                    st.write("**Pulse Rate Analysis:**")
                    st.plotly_chart(fig_pr_comparison, use_container_width=True)
                    with st.spinner('Analyzing pulse rate trends...'):
                        pr_analysis = analyze_pr_trends(sorted_results)
                        st.write(pr_analysis)
                        pulserate_analysis_content = AnalysisContent()
                        pulserate_analysis_content.sub_heading = "Pulse Rate Analysis"
                        pulserate_analysis_content.figure = fig_pr_comparison
                        pulserate_analysis_content.paragraph = pr_analysis
                        content_to_export.append(pulserate_analysis_content)
                    
                    st.markdown("---")
                    
                    # Total Hypoxic Time Chart
                    st.write("**Total Hypoxic Time Analysis:**")
                    st.plotly_chart(fig_hypoxic_time, use_container_width=True)
                    with st.spinner('Analyzing hypoxic time trends...'):
                        hypoxic_analysis = analyze_hypoxic_time(sorted_results)
                        st.write(hypoxic_analysis)
                        hypoxic_time_analysis_content = AnalysisContent()
                        hypoxic_time_analysis_content.sub_heading = "Total Hypoxic Time Analysis:"
                        hypoxic_time_analysis_content.figure = fig_hypoxic_time
                        hypoxic_time_analysis_content.paragraph = hypoxic_analysis
                        content_to_export.append(hypoxic_time_analysis_content)
                    
                    st.markdown("---")
                    
                    # BP Comparison Chart
                    st.write("**Blood Pressure Analysis:**")
                    st.plotly_chart(fig_bp_comparison, use_container_width=True)
                    with st.spinner('Analyzing BP trends...'):
                        bp_analysis = analyze_bp_trends(sorted_results)
                        st.write(bp_analysis)
                        bp_analysis_content = AnalysisContent()
                        bp_analysis_content.sub_heading = "Blood Pressure Analysis:"
                        bp_analysis_content.figure = fig_bp_comparison
                        bp_analysis_content.paragraph = bp_analysis
                        content_to_export.append(bp_analysis_content)
                else:
                    st.write("Upload multiple sessions to see progress charts")
                
                st.markdown("---")
                pdf_path = "exported_report.pdf"
                create_pdf(session_analysis_content, content_to_export, pdf_path)
                with open(pdf_path, "rb") as file:
                    pdf_bytes = file.read()

                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=pdf_path,
                    mime="application/pdf",
                )

                # Add the Detailed Treatment Overview section
                st.markdown('<h2 class="detailed-overview-header">Detailed Treatment Overview</h2>', unsafe_allow_html=True)

                if sorted_results:
                    st.markdown('<div class="detailed-overview-content">', unsafe_allow_html=True)
                    # Convert treatments to sorted list of tuples
                    sorted_treatments = sorted(sorted_results.items())
                    
                    # Group treatments into sets of 5
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
                    
                    # Create tabs for each group of 5
                    tab_labels = [f"Sessions {i*5-4}-{min(i*5, len(sorted_treatments))}" 
                                 for i in range(1, len(all_pages) + 1)]
                    tabs = st.tabs(tab_labels)
                    
                    # Define fields to display
                    fields = [
                        ('treatment_date', 'Treatment Date'),
                        ('total_duration', 'Total Duration'),
                        ('total_hypoxic_time', 'Total Hypoxic Time'),
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
                        ('pr_elevation_percent', 'PR Elevation (%)'),
                        ('bp_before_procedure', 'BP Before Procedure'),
                        ('bp_after_procedure', 'BP After Procedure')
                    ]
                    
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
                        </style>
                    """, unsafe_allow_html=True)
                    
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
                                    value = data.get(field_key, 'N/A')
                                    cols[i].markdown(f'<div class="field-value">{value}</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.write("Upload multiple sessions to see progress charts")

if __name__ == "__main__":
    main() 