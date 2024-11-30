# not working fully but getting there
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
            'treatments': {}  # Will store all data for each treatment
        }
        
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=True,
                use_text_flow=True
            )
            
            word_list = [w['text'].strip() for w in words]
            course_data['word_list'] = word_list
            
            # Process the word list to build relationships
            current_treatment = None
            current_header = None
            
            for i, word in enumerate(word_list):
                # Extract patient info
                if "Patient name" in word and i + 4 < len(word_list):
                    course_data['patient_name'] = word_list[i + 4]
                elif "Sex" in word and i + 4 < len(word_list):
                    course_data['sex'] = word_list[i + 4]
                elif "Date of birth" in word and i + 4 < len(word_list):
                    course_data['dob'] = word_list[i + 4]
                
                # Track treatment numbers
                elif word == "Treatment No.":
                    current_header = "Treatment No."
                    # Look ahead for treatment numbers
                    j = i + 1
                    while j < len(word_list):
                        try:
                            treatment_num = int(word_list[j])
                            if treatment_num not in course_data['treatments']:
                                course_data['treatments'][treatment_num] = {}
                            j += 1
                        except ValueError:
                            break
                
                # Process measurements
                elif word in ["Hypoxic O2 conc. (%)", "Min SpO2 Av. (%)", "Max SpO2 Av. (%)", 
                            "Min PR Av. (bpm)", "Max PR Av. (bpm)"]:
                    current_header = word
                    # Look ahead for values
                    j = i + 1
                    treatment_index = 0
                    while j < len(word_list):
                        try:
                            value = word_list[j]
                            # Try to convert to number (integer or float)
                            float(value)
                            # Find corresponding treatment number
                            treatment_nums = sorted(course_data['treatments'].keys())
                            if treatment_index < len(treatment_nums):
                                treatment_num = treatment_nums[treatment_index]
                                course_data['treatments'][treatment_num][current_header] = value
                            treatment_index += 1
                            j += 1
                        except ValueError:
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
            
            # Display patient information
            st.subheader("Patient Information")
            st.write(f"Patient Name: {course_data['patient_name']}")
            st.write(f"Sex: {course_data['sex']}")
            st.write(f"Date of Birth: {course_data['dob']}")
            
            # Display treatment data
            st.subheader("Treatment Data")
            for treatment_num in sorted(course_data['treatments'].keys()):
                st.write(f"\nTreatment {treatment_num}:")
                for measure, value in course_data['treatments'][treatment_num].items():
                    st.write(f"  {measure}: {value}")
            
            # Create DataFrame for comparison
            df = pd.DataFrame.from_dict(course_data['treatments'], orient='index')
            st.subheader("Comparison Table")
            st.dataframe(df)
            
            # Display raw word list with indices (for debugging)
            st.subheader("Raw Word List")
            for i, word in enumerate(course_data['word_list']):
                st.text(f"{i}: {word}")
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 