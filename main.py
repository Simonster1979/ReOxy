import streamlit as st
import pickle
from pathlib import Path

# Set page config first, before any other Streamlit commands
st.set_page_config(layout="wide")

# Import after setting page config
import app
import course_report

# Function to load persistent state
def load_persistent_state():
    state_path = Path(".streamlit/persistent_state.pkl")
    if state_path.exists():
        try:
            with open(state_path, "rb") as f:
                return pickle.load(f)
        except:
            pass
    return {}

# Function to save persistent state
def save_persistent_state(state):
    state_path = Path(".streamlit/persistent_state.pkl")
    state_path.parent.mkdir(exist_ok=True)
    with open(state_path, "wb") as f:
        pickle.dump(state, f)

# Load persistent state at startup
persistent_state = load_persistent_state()
if persistent_state.get('authenticated'):
    st.session_state.authenticated = True
    st.session_state.username = persistent_state.get('username')
else:
    st.session_state.authenticated = False

# Custom CSS for background
st.markdown("""
    <style>
        .stApp {
            background: rgb(255,255,255);
            background: radial-gradient(circle, rgba(255,255,255,1) 0%, rgba(255,255,255,1) 89%, rgba(218,216,216,1) 100%);
        }
        /* Hide "Select AI Model" section */
        [data-testid="stSidebarSelectbox"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# Hard-coded users
USERS = {
    'user': 'password',
    'user2': 'password2',
    'admin': 'adminpass'
}

def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        logo_col, title_col = st.columns([1, 1])
        
        with logo_col:
            st.image("assets/breathe-white.png", width=200)
        with title_col:
            st.markdown("")
            
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if username in USERS and USERS[username] == password:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    
                    # Save to persistent state
                    save_persistent_state({
                        'authenticated': True,
                        'username': username
                    })
                    
                    st.rerun()
                else:
                    st.error("Invalid username or password")

if not st.session_state.authenticated:
    login()
else:
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "ReOxy Reports"

    with st.sidebar:
        # Add logo at the top of sidebar
        st.image("assets/breathe-white.png", width=270)  # Adjust width as needed
        
        # Add some space after the logo
        st.markdown("---")  # Adds a horizontal line
        
        if st.button("Logout"):
            # Clear persistent state
            save_persistent_state({})
            st.session_state.clear()
            st.rerun()
        
        st.session_state.current_tab = st.radio("", ["ReOxy Reports", "Course Report"])

    if st.session_state.current_tab == "ReOxy Reports":
        app.main()
    else:
        course_report.main() 

# Replace the AI model selectbox with a hidden default
ai_model = "OpenAI GPT-3.5" #"Claude 3 Sonnet"  # Set default model