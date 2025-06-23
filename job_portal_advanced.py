import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime, date
from streamlit_option_menu import option_menu

# ---------- BACKGROUND IMAGE WITH OVERLAY ----------
def add_bg_with_overlay():
    st.markdown(
        """
        <style>
        .stApp {
            background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
                              url("https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1650&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        .css-18e3th9, .css-1d391kg {
            background-color: rgba(255, 255, 255, 0.88) !important;
            border-radius: 10px;
            padding: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

add_bg_with_overlay()

# ---------- CONFIG ----------
st.set_page_config(page_title="Smart Job Portal", layout="wide")

# ---------- DATABASE ----------
conn = sqlite3.connect("jobs.db", check_same_thread=False)
c = conn.cursor()

# Create users table
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT CHECK(role IN ('Employer', 'Employee'))
)
''')

# Create jobs table (initial)
c.execute('''
CREATE TABLE IF NOT EXISTS job_postings (
    id INTEGER PRIMARY KEY,
    company TEXT,
    role TEXT,
    experience INTEGER,
    projects TEXT,
    package TEXT,
    deadline TEXT
)
''')

# Ensure 'posted_by' column exists
try:
    c.execute("ALTER TABLE job_postings ADD COLUMN posted_by TEXT")
except sqlite3.OperationalError:
    pass

conn.commit()

# ---------- AUTH HELPERS ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_password(password)))
    return c.fetchone()

def register_user(username, password, role):
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (username, hash_password(password), role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# ---------- SESSION STATE ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

# ---------- LOGIN / SIGNUP ----------
menu = option_menu(
    menu_title="Welcome to 🧑🏻‍💻 Job Finder 🧑🏻‍💻",
    options=["Login", "Signup"],
    icons=["box-arrow-in-right", "person-plus"],
    orientation="horizontal",
)

if not st.session_state.logged_in:
    if menu == "Login":
        st.subheader("🔐 Login")
        login_username = st.text_input("Username")
        login_password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login_user(login_username, login_password)
            if user:
                st.success("✅ Logged in successfully")
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.session_state.role = user[3]
                st.rerun()
            else:
                st.error("❌ Invalid credentials")

    elif menu == "Signup":
        st.subheader("📝 Signup")
        signup_username = st.text_input("Choose a Username")
        signup_password = st.text_input("Choose a Password", type="password")
        role = st.radio("Signup as", ["Employer", "Employee"])
        if st.button("Create Account"):
            if register_user(signup_username, signup_password, role):
                st.success("🎉 Account created! Please login.")
            else:
                st.error("❌ Username already exists.")

# ---------- DASHBOARDS ----------
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.username} ({st.session_state.role})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()

    if st.session_state.role == "Employer":
        st.title("🏢 Employer Dashboard")
        st.subheader("Post a New Job")
        with st.form("post_form", clear_on_submit=True):
            company = st.text_input("Company Name")
            role = st.text_input("Job Role")
            experience = st.slider("Required Experience (Years)", 0, 10, 1)
            mini_projects = st.number_input("Mini Projects Required", 0)
            major_projects = st.number_input("Major Projects Required", 0)
            package = st.text_input("Package (LPA)")
            deadline = st.date_input("Deadline")
            post = st.form_submit_button("Post Job")
            if post:
                projects = f"{mini_projects}|{major_projects}"
                c.execute("INSERT INTO job_postings (company, role, experience, projects, package, deadline, posted_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (company, role, experience, projects, package, deadline.strftime("%Y-%m-%d"), st.session_state.username))
                conn.commit()
                st.success("✅ Job Posted")

        st.subheader("Your Posted Jobs")
        jobs = pd.read_sql_query("SELECT * FROM job_postings WHERE posted_by = ?", conn, params=(st.session_state.username,))
        for _, job in jobs.iterrows():
            mini, major = job['projects'].split('|')
            deadline_date = datetime.strptime(job['deadline'], "%Y-%m-%d").date()
            deadline_str = f"⏳ Deadline: {job['deadline']}"
            status = "⛔ Status: Closed" if deadline_date < date.today() else "✅ Status: Open"
            st.markdown(f"""
            **{job['role']}** @ {job['company']}  
            🗕 Exp: {job['experience']} yrs | 💰 {job['package']} LPA  
            🧹 Mini: {mini} | 🏗 Major: {major}  
            {deadline_str}  
            {status}
            """)
            if st.button(f"🗑 Delete {job['role']}", key=f"del_{job['id']}"):
                c.execute("DELETE FROM job_postings WHERE id = ?", (job['id'],))
                conn.commit()
                st.warning(f"🗑 Deleted {job['role']}")
                st.rerun()

    elif st.session_state.role == "Employee":
        st.title("👨‍🎓 Job Seeker Dashboard")
        st.subheader("Search Jobs")

        role_list = pd.read_sql_query("SELECT DISTINCT role FROM job_postings", conn)
        role_options = sorted(set(role_list['role'].dropna().str.title().tolist()))

        selected_role = st.selectbox("Select Job Role", role_options)
        desired_role = selected_role.lower() if selected_role else ""

        exp = st.slider("Your Experience (Years)", 0, 10, 1)
        mini = st.number_input("Mini Projects Done", 0)
        major = st.number_input("Major Projects Done", 0)

        if st.button("Search"):
            all_jobs = pd.read_sql_query("SELECT * FROM job_postings", conn)
            matched = []
            for _, job in all_jobs.iterrows():
                if job['role'].lower() == desired_role:
                    j_mini, j_major = map(int, job['projects'].split('|'))
                    if exp >= job['experience'] and mini >= j_mini and major >= j_major:
                        matched.append(job)
            if matched:
                for job in matched:
                    mini, major = job['projects'].split('|')
                    deadline_date = datetime.strptime(job['deadline'], "%Y-%m-%d").date()
                    deadline_str = f"⏳ Deadline: {job['deadline']}"
                    status = "⛔ Status: Closed" if deadline_date < date.today() else "✅ Status: Open"
                    st.markdown(f"""
                    **{job['role']}** @ {job['company']}  
                    📆 Experience Req. : {job['experience']} yrs | 💰 Package : {job['package']} LPA  
                    🧹 Mini Project Req. : {mini} | 🏗 Major Project Req. : {major}  
                    {deadline_str}  
                    {status}
                    """)
            else:
                st.warning("No matching jobs found.")