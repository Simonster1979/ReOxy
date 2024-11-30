import streamlit as st
import PyPDF2
import pandas as pd
import io
import re
import matplotlib.pyplot as plt

def extract_data_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    
    # Extract patient info
    patient_info = {}
    patient_info['name'] = re.search(r"Patient name\s*(.+)", text)
    patient_info['name'] = patient_info['name'].group(1) if patient_info['name'] else "N/A"
    patient_info['sex'] = re.search(r"Sex\s*(.+)", text)
    patient_info['sex'] = patient_info['sex'].group(1) if patient_info['sex'] else "N/A"
    patient_info['dob'] = re.search(r"Date of birth\s*(.+)", text)
    patient_info['dob'] = patient_info['dob'].group(1) if patient_info['dob'] else "N/A"
    
    # Extract treatment data
    treatments = re.findall(r"Treatment No\.(\d+)\s*Hypoxic O2 conc\. $$%$$\s*(\d+)\s*Procedure duration $$min:sec$$\s*(\d+:\d+)\s*Therapeutic SpO2 $$%$$\s*(\d+)", text)
    
    # Extract vital signs data
    vital_signs = re.findall(r"Treatment No\.(\d+)\s*Min SpO2 Av\. $$%$$\s*(\d+)\s*Max SpO2 Av\. $$%$$\s*(\d+)\s*Min PR Av\. $$bpm$$\s*(\d+)\s*Max PR Av\. $$bpm$$\s*(\d+)", text)
    
    # Extract blood pressure data
    bp_data = re.findall(r"Treatment No\.(\d+)\s*BP SYS before $$mmHg$$\s*(\d+)\s*BP DIA before $$mmHg$$\s*(\d+)\s*BP SYS after $$mmHg$$\s*(\d+)\s*BP DIA after $$mmHg$$\s*(\d+)", text)
    
    # Convert to DataFrames
    treatments_df = pd.DataFrame(treatments, columns=['Treatment No.', 'Hypoxic O2 conc. (%)', 'Procedure duration', 'Therapeutic SpO2 (%)'])
    vital_signs_df = pd.DataFrame(vital_signs, columns=['Treatment No.', 'Min SpO2 Av. (%)', 'Max SpO2 Av. (%)', 'Min PR Av. (bpm)', 'Max PR Av. (bpm)'])
    bp_df = pd.DataFrame(bp_data, columns=['Treatment No.', 'BP SYS before (mmHg)', 'BP DIA before (mmHg)', 'BP SYS after (mmHg)', 'BP DIA after (mmHg)'])
    
    return patient_info, treatments_df, vital_signs_df, bp_df

def plot_comparison(data, title, y_label):
    fig, ax = plt.subplots(figsize=(10, 6))
    for patient, df in data:
        ax.plot(df['Treatment No.'], df[y_label], label=patient)
    ax.set_xlabel('Treatment No.')
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.legend()
    return fig

def main():
    st.title("Medical Treatment PDF Comparison App")

    uploaded_files = st.file_uploader("Choose PDF files", accept_multiple_files=True, type="pdf")

    if uploaded_files:
        all_data = []
        for uploaded_file in uploaded_files:
            try:
                patient_info, treatments_df, vital_signs_df, bp_df = extract_data_from_pdf(uploaded_file)
                all_data.append((patient_info['name'], treatments_df, vital_signs_df, bp_df))
                
                st.subheader(f"Patient: {patient_info['name']}")
                st.write(f"Sex: {patient_info['sex']}")
                st.write(f"Date of Birth: {patient_info['dob']}")
                
                st.write("Treatment Data:")
                st.dataframe(treatments_df)
                
                st.write("Vital Signs Data:")
                st.dataframe(vital_signs_df)
                
                st.write("Blood Pressure Data:")
                st.dataframe(bp_df)
            except Exception as e:
                st.error(f"Error processing file {uploaded_file.name}: {str(e)}")

        if len(all_data) > 1:
            st.subheader("Data Comparison")
            
            comparison_options = [
                "Therapeutic SpO2 (%)",
                "Min SpO2 Av. (%)",
                "Max SpO2 Av. (%)",
                "Min PR Av. (bpm)",
                "Max PR Av. (bpm)",
                "BP SYS before (mmHg)",
                "BP DIA before (mmHg)",
                "BP SYS after (mmHg)",
                "BP DIA after (mmHg)"
            ]
            
            selected_comparison = st.selectbox("Select data to compare:", comparison_options)
            
            if selected_comparison in ["Therapeutic SpO2 (%)"]:
                comparison_data = [(name, df) for name, df, _, _ in all_data]
            elif selected_comparison in ["Min SpO2 Av. (%)", "Max SpO2 Av. (%)", "Min PR Av. (bpm)", "Max PR Av. (bpm)"]:
                comparison_data = [(name, df) for name, _, df, _ in all_data]
            else:
                comparison_data = [(name, df) for name, _, _, df in all_data]
            
            fig = plot_comparison(comparison_data, f"Comparison of {selected_comparison}", selected_comparison)
            st.pyplot(fig)

if __name__ == "__main__":
    main()

