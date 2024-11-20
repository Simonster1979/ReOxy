import streamlit as st
import pdfplumber
import io
from collections import OrderedDict
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openai():
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        org_id = os.getenv("OPENAI_ORG_ID")
        
        client = OpenAI(
            api_key=api_key,
            organization=org_id
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        st.success("OpenAI is configured correctly!")
        return True
    except Exception as e:
        st.error(f"OpenAI configuration error: {str(e)}")
        st.write("Full error:", str(e))
        return False

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

def summarize_report(patient_data):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"""
        Summarize this ReOxy treatment data:
        Patient: {patient_data['patient_name']}
        Treatment Date: {patient_data['treatment_date']}
        Key Metrics:
        - Total Duration: {patient_data['total_duration']}
        - Total Hypoxic Time: {patient_data['total_hypoxic_time']}
        - Min SpO2 Average: {patient_data['min_spo2_average']}
        - Max SpO2 Average: {patient_data['max_spo2_average']}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def compare_sessions(sorted_results):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sessions_data = []
        for treatment_num, data in sorted_results.items():
            sessions_data.append(f"""
            Session {treatment_num}:
            - Duration: {data['total_duration']}
            - Hypoxic Time: {data['total_hypoxic_time']}
            - Min SpO2: {data['min_spo2_average']}
            - Max SpO2: {data['max_spo2_average']}
            """)
        
        prompt = f"Compare these ReOxy treatment sessions and highlight key differences:\n{''.join(sessions_data)}"
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
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

def main():
    st.set_page_config(layout="wide")
    st.title("ReOxy Reports Interpreter")
    
    # Add OpenAI test button at the top
    if st.button("Test OpenAI Connection"):
        test_openai()
    
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
        st.session_state.uploaded_files = []
                    
        # Process new files
       
        for file in new_files:
            file_copy = io.BytesIO(file.read())
            file_copy.name = file.name
            file.seek(0)
            st.session_state.uploaded_files.append(file_copy)
        
        # Process uploaded files and extract data
        all_results = {}
        first_patient = None  # Initialize variable to hold the first patient's data

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
            
            # Create three columns for the different analyses
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("Session Summary")
                # Get the latest session data
                latest_session = sorted_results[max(sorted_results.keys())]
                summary = summarize_report(latest_session)
                st.write(summary)
            
            with col2:
                st.subheader("Session Comparison")
                if len(sorted_results) > 1:
                    comparison = compare_sessions(sorted_results)
                    st.write(comparison)
                else:
                    st.write("Upload multiple sessions to see comparison")
            
            with col3:
                st.subheader("Treatment Recommendations")
                recommendations = generate_recommendations(latest_session)
                st.write(recommendations)
            
            # Add a separator before the table
            st.markdown("---")
            
            # Continue with your existing table display code
            st.subheader("Extracted Results")

            # Create a table header
            cols = st.columns(len(sorted_results) + 1)  # +1 for labels column

            # Labels column
            ## cols[0].write("Field")
            for i, (treatment_num, data) in enumerate(sorted_results.items(), 1):
                cols[i].write(f"Session {treatment_num}")

            # Data rows
            fields = [
              ##  ('patient_name', 'Patient Name'),
              ##  ('reference_number', 'Reference Number'),
              ##  ('sex', 'Sex'),
              ##  ('date_of_birth', 'Date of Birth'),
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