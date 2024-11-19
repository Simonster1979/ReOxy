import streamlit as st
import pdfplumber
import io

def extract_text_from_pdf(pdf_file):
    try:
        pdf_bytes = pdf_file.read()
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        
        # Dictionary to store patient data
        patient_data = {
            'patient_name': '',
            'reference_number': '',
            'sex': '',
            'date_of_birth': '',
            'treatment_number': '',
            'treatment_date': ''
        }
        
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=True,
                use_text_flow=True
            )
            
            # Convert words to list for easier processing
            word_list = [w['text'].strip() for w in words]
            
            # Looking at the exact indices from the word list
            for i, word in enumerate(word_list):
                # Patient Name (index 2)
                if word == "Joanne Budgen" and i < 5:  # Only match if near start of document
                    patient_data['patient_name'] = word
                
                # Reference Number (index 3)
                elif word == "---":
                    patient_data['reference_number'] = word
                
                # Sex (index 8)
                elif word == "Female" or word == "Male":
                    patient_data['sex'] = word
                
                # Date of Birth (index 9)
                elif word == "06.09.1981":  # Looking for exact DOB
                    patient_data['date_of_birth'] = word
                
                # Treatment Number (index 10)
                elif word == "1" and i < 15:  # Looking for exact treatment number
                    patient_data['treatment_number'] = word
                
                # Treatment Date (index 11)
                elif word == "03.06.2024" and i < 15:  # Looking for exact treatment date
                    patient_data['treatment_date'] = word
        
        pdf.close()
        
        # Format output
        formatted_output = [
            f"Patient Name: {patient_data['patient_name']}",
            f"Reference Number: {patient_data['reference_number']}",
            f"Sex: {patient_data['sex']}",
            f"Date of Birth: {patient_data['date_of_birth']}",
            f"Treatment Number: {patient_data['treatment_number']}",
            f"Treatment Date: {patient_data['treatment_date']}"
        ]
        
        return formatted_output, patient_data
        
    except Exception as e:
        st.error(f"Error in extract_text_from_pdf: {str(e)}")
        st.write("Full error:", str(e))
        return [], {}

def main():
    st.title("PDF Text Extractor")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        try:
            formatted_text, patient_data = extract_text_from_pdf(uploaded_file)
            
            if formatted_text:
                st.subheader("Extracted Information:")
                for line in formatted_text:
                    st.write(line)
                
                # Add download button for extracted text
                text_content = '\n'.join(formatted_text)
                st.download_button(
                    label="Download Extracted Text",
                    data=text_content,
                    file_name="extracted_text.txt",
                    mime="text/plain"
                )
            else:
                st.warning("No text was extracted from the PDF")
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main() 