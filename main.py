import streamlit as st

# Set page config first, before any other Streamlit commands
st.set_page_config(layout="wide")

# Import after setting page config
import app
import course_report

# Initialize session state for tab selection if it doesn't exist
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "ReOxy Reports"

# Create radio buttons in sidebar for navigation
with st.sidebar:
    st.session_state.current_tab = st.radio("", ["ReOxy Reports", "Course Report"])

# Show the selected page
if st.session_state.current_tab == "ReOxy Reports":
    app.main()
else:
    course_report.main() 