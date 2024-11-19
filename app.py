import streamlit as st
import pdfplumber
import io
from collections import OrderedDict
import pandas as pd

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

def main():
    st.title("PDF Text Extractor")
    
    # Create a session state to store uploaded files if it doesn't exist
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    # Add a clear button before the file uploader
    if st.button("Clear all files"):
        st.session_state.uploaded_files = []
        st.session_state.clear()  # This will clear all session state, including the file uploader
        st.rerun()
    
    # File uploader
    new_files = st.file_uploader(
        "Choose PDF files", 
        type="pdf", 
        accept_multiple_files=True,
        key='pdf_uploader'
    )
    
    # Add new files to session state
    if new_files:
        # Get filenames of existing files
        existing_filenames = {f.name for f in st.session_state.uploaded_files}
        
        # Add only new files that aren't already in the list
        for file in new_files:
            if file.name not in existing_filenames:
                # Create a new BytesIO object with the file content
                file_copy = io.BytesIO(file.read())
                file_copy.name = file.name  # Preserve the filename
                file.seek(0)  # Reset the original file pointer
                st.session_state.uploaded_files.append(file_copy)
    
    # Show currently uploaded files with remove buttons
    if st.session_state.uploaded_files:
        st.write(f"Currently uploaded files ({len(st.session_state.uploaded_files)}):")
        files_to_remove = []
        
        # Create columns for each file
        for file in st.session_state.uploaded_files:
            col1, col2 = st.columns([6, 1])
            with col1:
                st.write(f"- {file.name}")
            with col2:
                if st.button("✖", key=f"remove_{file.name}"):
                    files_to_remove.append(file)
        
        # Remove files marked for removal
        if files_to_remove:
            for file in files_to_remove:
                st.session_state.uploaded_files.remove(file)
            st.rerun()
        
        # Dictionary to store all results, keyed by treatment number
        all_results = {}
        
        # Process each uploaded file
        for uploaded_file in st.session_state.uploaded_files:
            try:
                # Reset file pointer before processing
                uploaded_file.seek(0)
                formatted_text, patient_data = extract_text_from_pdf(uploaded_file)
                
                # Use treatment number as key
                treatment_num = int(patient_data['treatment_number'])
                all_results[treatment_num] = patient_data
                
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        if all_results:
            # Sort results by treatment number
            sorted_results = OrderedDict(sorted(all_results.items()))
            
            # Create a table header
            cols = st.columns(len(sorted_results) + 1)  # +1 for labels column
            
            # Labels column
            cols[0].write("Field")
            for i, (treatment_num, data) in enumerate(sorted_results.items(), 1):
                cols[i].write(f"Session {treatment_num}")
            
            # Data rows
            fields = [
                ('patient_name', 'Patient Name'),
                ('reference_number', 'Reference Number'),
                ('sex', 'Sex'),
                ('date_of_birth', 'Date of Birth'),
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