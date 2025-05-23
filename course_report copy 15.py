import pdfplumber
import io
import streamlit as st
import re
from pathlib import Path
import pandas as pd
from anthropic import Anthropic
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from openai import OpenAI
import anthropic
from fpdf import FPDF
import base64
from datetime import datetime

# Load environment variables
load_dotenv()

ANALYSIS_STRATEGIES = {
    "Analysis Depth": {
        "Comprehensive Analysis": "Provide a detailed, thorough analysis with in-depth examination of all metrics and their relationships",
        "Standard Overview": "Give a balanced analysis covering key points and notable findings",
        "Quick Summary": "Provide a concise summary focusing only on the most critical findings"
    },
    "Language Style": {
        "Technical": "Use precise medical and technical terminology appropriate for healthcare professionals",
        "Plain Language": "Explain findings in clear, simple terms avoiding technical jargon",
        "ELI5": "Break down concepts into their simplest form using analogies and simple explanations"
    },
    "Focus Areas": {
        "Clinical Outcomes": "Emphasize treatment effectiveness and patient response patterns",
        "Safety & Monitoring": "Focus on safety parameters and risk management aspects",
        "Progress Tracking": "Highlight changes and improvements across sessions",
        "Future Planning": "Emphasize recommendations and future treatment strategies"
    },
    "Analysis Structure": {
        "Systematic Breakdown": "Analyze each aspect methodically with clear categorization",
        "Problem-Solution": "Identify challenges and provide specific solutions",
        "Comparative Analysis": "Focus on comparing results across sessions and identifying patterns",
        "Action-Oriented": "Emphasize practical next steps and actionable recommendations"
    }
}

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
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Get selected strategies from session state
        strategies = {
            "Analysis Depth": st.session_state.get("strategy_Analysis Depth", "Standard Overview"),
            "Language Style": st.session_state.get("strategy_Language Style", "Plain Language"),
            "Focus Areas": st.session_state.get("strategy_Focus Areas", "Clinical Outcomes"),
            "Analysis Structure": st.session_state.get("strategy_Analysis Structure", "Systematic Breakdown")
        }
        
        # Build strategy instructions
        strategy_instructions = "\n".join([
            f"Analysis Approach:",
            f"- Depth: {ANALYSIS_STRATEGIES['Analysis Depth'][strategies['Analysis Depth']]}",
            f"- Style: {ANALYSIS_STRATEGIES['Language Style'][strategies['Language Style']]}",
            f"- Focus: {ANALYSIS_STRATEGIES['Focus Areas'][strategies['Focus Areas']]}",
            f"- Structure: {ANALYSIS_STRATEGIES['Analysis Structure'][strategies['Analysis Structure']]}"
        ])
        
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
        
        prompt = f"""Based on the following analysis approach and patient data, provide a targeted analysis:

        {strategy_instructions}

        Case History:
        {case_history}

        Treatment Data:
        - Total Sessions: {len(analysis_data['treatments'])}
        - Patient Name: {analysis_data.get('patient_name', 'N/A')}
        - Sex: {analysis_data.get('sex', 'N/A')}
        - Date of Birth: {analysis_data.get('dob', 'N/A')}

        Detailed Treatment Results:
        {''.join(treatment_data)}

        Please analyze according to the specified approach, focusing on:
        1. How the patient's medical history relates to their treatment responses
        2. Any patterns in vital signs that correlate with their medical history
        3. Potential implications for future treatment based on history and responses
        """
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,  # Increased token limit to accommodate more detailed responses
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing case history: {str(e)}"

def compare_sessions(course_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        sessions_data = []
        
        # Get selected strategies from session state
        strategies = {
            "Analysis Depth": st.session_state.get("strategy_Analysis Depth", "Standard Overview"),
            "Language Style": st.session_state.get("strategy_Language Style", "Plain Language"),
            "Focus Areas": st.session_state.get("strategy_Focus Areas", "Clinical Outcomes"),
            "Analysis Structure": st.session_state.get("strategy_Analysis Structure", "Systematic Breakdown")
        }
        
        # Build strategy instructions
        strategy_instructions = "\n".join([
            f"Analysis Approach:",
            f"- Depth: {ANALYSIS_STRATEGIES['Analysis Depth'][strategies['Analysis Depth']]}",
            f"- Style: {ANALYSIS_STRATEGIES['Language Style'][strategies['Language Style']]}",
            f"- Focus: {ANALYSIS_STRATEGIES['Focus Areas'][strategies['Focus Areas']]}",
            f"- Structure: {ANALYSIS_STRATEGIES['Analysis Structure'][strategies['Analysis Structure']]}"
        ])

        for treatment_num, data in course_data['treatments'].items():
            # Extract key metrics (existing code)
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

        prompt = f"""Based on the following analysis approach and treatment sessions data, provide a targeted analysis:

        {strategy_instructions}

        Analyze the following ReOxy treatment sessions and provide insights on:
        1. Changes in SpO2 tolerance and adaptation between sessions
        2. Heart rate response patterns and cardiovascular adaptation
        3. Changes in treatment duration and number of cycles
        4. Overall progression in hypoxic tolerance
        
        Treatment Data:{''.join(sessions_data)}
        
        Provide an analysis according to the specified approach, highlighting key trends, improvements, or areas of note between sessions."""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def generate_recommendations(course_data):
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

def analyze_phase_durations(analysis_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in analysis_data['treatments'].items():
            sessions_data.append(f"""
            Session {treatment_num}:
            - Hypoxic Phase Duration: {data.get('Hypox. Phase dur. Av. (min:sec)', 'N/A')}
            - Hyperoxic Phase Duration: {data.get('Hyperox. Phase dur. Av. (min:sec)', 'N/A')}
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

def analyze_pulse_rate_trends(analysis_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in analysis_data['treatments'].items():
            sessions_data.append(f"""
            Session {treatment_num}:
            - Min PR Average: {data.get('Min PR Av. (bpm)', 'N/A')}
            - Max PR Average: {data.get('Max PR Av. (bpm)', 'N/A')}
            """)
        
        prompt = f"""Analyze the Pulse Rate averages trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between Min and Max Pulse Rate averages
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing pulse rate trends: {str(e)}"

def analyze_total_hypoxic_time(analysis_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in analysis_data['treatments'].items():
            # Calculate total hypoxic time
            try:
                hypoxic_dur = data.get('Hypox. Phase dur. Av. (min:sec)', 'N/A')
                cycles = data.get('Number of cycles', 'N/A')
                if hypoxic_dur != 'N/A' and cycles != 'N/A':
                    min_sec = hypoxic_dur.split(':')
                    total_seconds = int(min_sec[0]) * 60 + int(min_sec[1])
                    num_cycles = int(cycles.split()[0])
                    total_minutes = (total_seconds * num_cycles) / 60
                    sessions_data.append(f"""
                    Session {treatment_num}:
                    - Total Hypoxic Time: {total_minutes:.1f} minutes
                    """)
            except (ValueError, IndexError):
                continue
        
        prompt = f"""Analyze the Total Hypoxic time trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between total hypoxic time durations
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing total hypoxic time: {str(e)}"

def analyze_bp_trends(analysis_data):
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        sessions_data = []
        for treatment_num, data in analysis_data['treatments'].items():
            sys_before = data.get('BP SYS before (mmHg)', 'N/A')
            dia_before = data.get('BP DIA before (mmHg)', 'N/A')
            sys_after = data.get('BP SYS after (mmHg)', 'N/A')
            dia_after = data.get('BP DIA after (mmHg)', 'N/A')
            
            sessions_data.append(f"""
            Session {treatment_num}:
            - BP Before: {sys_before}/{dia_before}
            - BP After: {sys_after}/{dia_after}
            """)
        
        prompt = f"""Analyze the BP trends across these ReOxy sessions in 2-3 sentences. Focus on:
        1. The relationship between BP before and after treatment
        2. What these trends indicate about the patient's adaptive response to treatment

        Sessions data:{''.join(sessions_data)}"""
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error analyzing BP trends: {str(e)}"

def compare_sessions_openai(analysis_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sessions_data = []
        
        # Get selected strategies from session state
        strategies = {
            "Analysis Depth": st.session_state.get("strategy_Analysis Depth", "Standard Overview"),
            "Language Style": st.session_state.get("strategy_Language Style", "Plain Language"),
            "Focus Areas": st.session_state.get("strategy_Focus Areas", "Clinical Outcomes"),
            "Analysis Structure": st.session_state.get("strategy_Analysis Structure", "Systematic Breakdown")
        }
        
        # Build strategy instructions
        strategy_instructions = "\n".join([
            f"Analysis Approach:",
            f"- Depth: {ANALYSIS_STRATEGIES['Analysis Depth'][strategies['Analysis Depth']]}",
            f"- Style: {ANALYSIS_STRATEGIES['Language Style'][strategies['Language Style']]}",
            f"- Focus: {ANALYSIS_STRATEGIES['Focus Areas'][strategies['Focus Areas']]}",
            f"- Structure: {ANALYSIS_STRATEGIES['Analysis Structure'][strategies['Analysis Structure']]}"
        ])
        
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

        prompt = f"""Based on the following analysis approach and treatment sessions data, provide a targeted analysis:

        {strategy_instructions}

        Analyze the following ReOxy treatment sessions and provide insights on:
        1. Changes in SpO2 tolerance and adaptation between sessions
        2. Heart rate response patterns and cardiovascular adaptation
        3. Changes in treatment duration and number of cycles
        4. Overall progression in hypoxic tolerance
        
        Treatment Data:{''.join(sessions_data)}
        
        Provide an analysis according to the specified approach, highlighting key trends, improvements, or areas of note between sessions."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error comparing sessions: {str(e)}"

def generate_recommendations_openai(analysis_data):
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

        prompt = f"""Based on the following ReOxy treatment sessions data, provide specific recommendations for future treatments. Consider:
        1. Whether to adjust hypoxic oxygen concentration
        2. Suggestions for treatment duration and number of cycles
        3. Target SpO2 ranges based on patient's adaptation
        4. Safety considerations based on observed responses
        
        Treatment Data:{''.join(sessions_data)}
        
        Provide 3-4 specific, actionable recommendations for optimizing future treatments."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def create_pdf_report(analysis_data, case_history, charts, analysis_results):
    """
    Create a PDF report from the analysis data
    
    Args:
        analysis_data: Dictionary containing treatment data
        case_history: String containing patient case history
        charts: Dictionary containing chart images
        analysis_results: Dictionary containing analysis text
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Add header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'ReOxy Treatment Analysis Report', 0, 1, 'C')
    pdf.ln(5)
    
    # Add date
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Report Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'R')
    
    # Patient Information
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Patient Information', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Name: {analysis_data["patient_name"]}', 0, 1)
    pdf.cell(0, 10, f'Date of Birth: {analysis_data["dob"]}', 0, 1)
    pdf.cell(0, 10, f'Sex: {analysis_data["sex"]}', 0, 1)
    
    # Case History
    if case_history.strip():
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Case History', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 10, case_history)
        pdf.ln(5)
    
    # Analysis Results
    if analysis_results.get('case_history_analysis'):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Case History Analysis', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 10, analysis_results['case_history_analysis'])
        pdf.ln(5)
    
    # Add charts
    for chart_title, chart_img in charts.items():
        pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, chart_title, 0, 1, 'C')
        pdf.image(chart_img, x=10, y=None, w=190)
        pdf.ln(5)
    
    # Treatment Recommendations
    if analysis_results.get('recommendations'):
        pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Treatment Recommendations', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 10, analysis_results['recommendations'])
    
    return pdf

def main():
    # Add AI model selector to sidebar
    ai_model = st.sidebar.selectbox(
        "Select AI Model",
        ["OpenAI GPT-3.5","Claude 3 Sonnet"]
    )
    
    st.title("Course Report PDF Extractor")
    
    # Add custom CSS for print styling
    st.markdown("""
        <style>
            @media print {
                /* Keep charts together */
                .element-container {
                    break-inside: avoid !important;
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
                    margin: 2cm;
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
                
                /* Increase font sizes for print */
                h1 {
                    font-size: 32pt !important;
                }
                
                h2, h3, .stSubheader {
                    font-size: 26pt !important;
                }
                
                p, div, span {
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

                /* Hide patient case history section */
                .patient-case-history {
                    display: none !important;
                }
                [data-testid="stTextArea"], 
                .stTextArea > label {
                    display: none !important;
                }

                /* Keep Detailed Treatment Overview on whole page */
                .detailed-overview-header {
                    break-before: page !important;
                    break-after: avoid !important;
                }
                
                /* Keep the overview content together */
                .detailed-overview-content {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                }
                
                /* Keep field groups together */
                .field-group {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                    margin-bottom: 20px !important;
                }
                
                /* Ensure table rows stay together */
                tr {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                }
                
                /* Keep table headers with their content */
                thead {
                    display: table-header-group !important;
                }
                
                tbody {
                    break-inside: avoid !important;
                }

                /* Reduce spacing after title */
                h1 {
                    margin-bottom: 0 !important;
                    padding-bottom: 0 !important;
                }
                
                /* Reduce spacing between elements */
                .block-container {
                    padding-top: 0 !important;
                    margin-top: 0 !important;
                }
                
                /* Adjust first element spacing */
                .block-container > div:first-child {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
                }
                
                /* Remove extra padding from Streamlit containers */
                .element-container {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
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
    if 'current_file_name' not in st.session_state:
        st.session_state.current_file_name = None
    
    # Wrap the case history section in a div with the print-hiding class
    with st.container():
        # First show Analysis Strategies
        st.markdown('<div class="analysis-strategies">', unsafe_allow_html=True)
        st.subheader("Analysis Strategies")
        
        # Create four columns for strategy options
        col1, col2, col3, col4 = st.columns(4)
        selected_strategies = {}
        
        # Analysis Depth in first column
        with col1:
            st.markdown("**Analysis Depth**")
            selected_strategy = st.radio(
                "Select Analysis Depth:",
                options=list(ANALYSIS_STRATEGIES["Analysis Depth"].keys()),
                key="strategy_Analysis Depth",
                label_visibility="collapsed"
            )
            selected_strategies["Analysis Depth"] = {
                "selection": selected_strategy,
                "instruction": ANALYSIS_STRATEGIES["Analysis Depth"][selected_strategy]
            }
        
        # Language Style in second column
        with col2:
            st.markdown("**Language Style**")
            selected_strategy = st.radio(
                "Select Language Style:",
                options=list(ANALYSIS_STRATEGIES["Language Style"].keys()),
                key="strategy_Language Style",
                label_visibility="collapsed"
            )
            selected_strategies["Language Style"] = {
                "selection": selected_strategy,
                "instruction": ANALYSIS_STRATEGIES["Language Style"][selected_strategy]
            }
        
        # Focus Areas in third column
        with col3:
            st.markdown("**Focus Areas**")
            selected_strategy = st.radio(
                "Select Focus Areas:",
                options=list(ANALYSIS_STRATEGIES["Focus Areas"].keys()),
                key="strategy_Focus Areas",
                label_visibility="collapsed"
            )
            selected_strategies["Focus Areas"] = {
                "selection": selected_strategy,
                "instruction": ANALYSIS_STRATEGIES["Focus Areas"][selected_strategy]
            }
        
        # Analysis Structure in fourth column
        with col4:
            st.markdown("**Analysis Structure**")
            selected_strategy = st.radio(
                "Select Analysis Structure:",
                options=list(ANALYSIS_STRATEGIES["Analysis Structure"].keys()),
                key="strategy_Analysis Structure",
                label_visibility="collapsed"
            )
            selected_strategies["Analysis Structure"] = {
                "selection": selected_strategy,
                "instruction": ANALYSIS_STRATEGIES["Analysis Structure"][selected_strategy]
            }
        
        st.markdown('</div>', unsafe_allow_html=True)

        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Then show Patient Case History
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
    
    # Check if file has changed (either new file uploaded or file removed)
    if uploaded_file is None:
        # File was removed or no file uploaded yet
        st.session_state.course_data = None
        st.session_state.selected_treatments = []
        st.session_state.show_analysis = False
        st.session_state.analyzed_treatments = []
        st.session_state.current_file_name = None
    elif uploaded_file is not None and (st.session_state.current_file_name != uploaded_file.name):
        # New file uploaded - process it
        with st.spinner('Loading report...'):
            try:
                st.session_state.course_data = extract_course_report(uploaded_file)
                st.session_state.current_file_name = uploaded_file.name
                st.session_state.selected_treatments = []
                st.session_state.show_analysis = False
                st.session_state.analyzed_treatments = []
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
                st.write(f"Found: {len(treatment_numbers)} Treatments")
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
                st.subheader("Patient Information")
                st.write(f"**Patient Name:** {analysis_data['patient_name']}")
                st.write(f"**Date of Birth:** {analysis_data['dob']}")
                st.write(f"**Sex:** {analysis_data['sex']}")
                
                # Add case history analysis if text was entered
                if case_history.strip():
                    st.subheader("Case History Analysis")
                    with st.spinner('Analyzing case history...'):
                        history_analysis = analyze_case_history(case_history, analysis_data)
                        st.write(history_analysis)
                
                # Add a separator
                st.markdown("---")
                
                # Session comparison
                if len(filtered_treatments) > 1:
                    st.subheader("Session Comparison")
                    with st.spinner('Analyzing treatment sessions...'):
                        comparison = compare_sessions_openai(analysis_data) if ai_model == "OpenAI GPT-3.5" else compare_sessions(analysis_data)
                        st.write(comparison)
                
                # Treatment recommendations
                st.subheader("Treatment Recommendations")
                with st.spinner('Generating treatment recommendations...'):
                    recommendations = generate_recommendations_openai(analysis_data) if ai_model == "OpenAI GPT-3.5" else generate_recommendations(analysis_data)
                    st.write(recommendations)
                
                # Add a separator
               # st.markdown("---")
                
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
                st.markdown("---")
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
                    
                    # Create two columns for analysis and chart
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write("**Phase Duration Analysis:**")
                        with st.spinner('Analyzing phase durations...'):
                            phase_analysis = analyze_phase_durations(analysis_data)
                            st.write(phase_analysis)
                    
                    with col2:
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
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=50, b=100),
                            height=500
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
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
                    
                    # Create two columns for analysis and chart
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write("**Pulse Rate Analysis:**")
                        with st.spinner('Analyzing pulse rate trends...'):
                            pr_analysis = analyze_pulse_rate_trends(analysis_data)
                            st.write(pr_analysis)
                    
                    with col2:
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
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=50, b=100),
                            height=500
                        )
                        
                        st.plotly_chart(fig_pr, use_container_width=True)
                    
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
                    
                    # Create two columns for analysis and chart
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write("**Total Hypoxic Time Analysis:**")
                        with st.spinner('Analyzing hypoxic time trends...'):
                            hypoxic_time_analysis = analyze_total_hypoxic_time(analysis_data)
                            st.write(hypoxic_time_analysis)
                    
                    with col2:
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
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=50, b=100),
                            height=500
                        )
                        
                        st.plotly_chart(fig_hypoxic, use_container_width=True)
                    
                    st.markdown("---")
                    
                    # Create data for blood pressure chart
                    bp_before = []
                    bp_after = []
                    
                    for treatment_num, data in sorted(analysis_data['treatments'].items()):
                        # Process BP before
                        sys_before = data.get('BP SYS before (mmHg)', 'N/A')
                        dia_before = data.get('BP DIA before (mmHg)', 'N/A')
                        if sys_before != 'N/A' and dia_before != 'N/A':
                            bp_before.append(f"{sys_before}/{dia_before}")
                        else:
                            bp_before.append(None)
                        
                        # Process BP after
                        sys_after = data.get('BP SYS after (mmHg)', 'N/A')
                        dia_after = data.get('BP DIA after (mmHg)', 'N/A')
                        if sys_after != 'N/A' and dia_after != 'N/A':
                            bp_after.append(f"{sys_after}/{dia_after}")
                        else:
                            bp_after.append(None)
                    
                    # Create two columns for analysis and chart
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write("**Blood Pressure Analysis:**")
                        with st.spinner('Analyzing BP trends...'):
                            bp_analysis = analyze_bp_trends(analysis_data)
                            st.write(bp_analysis)
                    
                    with col2:
                        # Create BP chart
                        fig_bp = go.Figure()
                        
                        fig_bp.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=bp_before,
                            name='BP Before',
                            mode='lines+markers',
                            line=dict(color='royalblue')
                        ))
                        
                        fig_bp.add_trace(go.Scatter(
                            x=treatment_nums,
                            y=bp_after,
                            name='BP After',
                            mode='lines+markers',
                            line=dict(color='firebrick')
                        ))
                        
                        fig_bp.update_layout(
                            title='Blood Pressure Trends Across Sessions',
                            xaxis_title='Session Number',
                            yaxis_title='Blood Pressure (systolic/diastolic mmHg)',
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=12)
                            ),
                            margin=dict(t=50, l=50, r=50, b=100),
                            height=500
                        )
                        
                        st.plotly_chart(fig_bp, use_container_width=True)
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

