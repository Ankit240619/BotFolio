
import streamlit as st
import pandas as pd
import requests
import datetime
import base64
from dotenv import load_dotenv
import os
import json
import time

# Load environment variables
load_dotenv()


API_URL ="https://botfolio-apis-548112246073.us-central1.run.app"
# API_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="BotFolio Job Tool", 
    page_icon="🔍", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Add custom CSS for better styling
st.markdown("""
<style>
    /* Job card styling */
    .job-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 25px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .job-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .job-title {
        color: #2c3e50;
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 8px;
    }
    .job-company {
        color: #3498db;
        font-weight: bold;
        font-size: 18px;
        margin-bottom: 8px;
    }
    .job-meta {
        margin-bottom: 10px;
        font-size: 14px;
        color: #555;
    }
    .job-role-tag {
        display: inline-block;
        background-color: #e1f5fe;
        color: #0288d1;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 13px;
        margin-right: 5px;
    }
    .job-date {
        color: #7f8c8d;
        font-size: 14px;
        margin-top: 5px;
        margin-bottom: 15px;
    }
    .job-buttons {
        display: flex;
        gap: 10px;
        margin-top: 15px;
    }
    .view-button, .prep-button {
        display: inline-block;
        padding: 8px 16px;
        text-decoration: none !important;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
        border: none;
        cursor: pointer;
        transition: background-color 0.2s;
        color: white !important;
    }
    .view-button {
        background-color: #3498db;
    }
    .view-button:hover {
        background-color: #2980b9;
    }
    .prep-button {
        background-color: #2ecc71;
    }
    .prep-button:hover {
        background-color: #27ae60;
    }

    .skills-title {
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        color: #3498db;
    }
    .skill-tag {
        display: inline-block;
        background-color: #e8f4fc;
        color: #3498db;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 13px;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    
    /* QA Pipeline Styling */
    .qa-container {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .qa-question {
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 8px;
        font-size: 18px;
        color: #2c3e50;
        padding: 10px;
        background-color: #f8f9fa;
        border-left: 3px solid #3498db;
        border-radius: 5px;
    }
    .qa-answer {
        margin-bottom: 20px;
    }
    .qa-nav-buttons {
        display: flex;
        justify-content: space-between;
        margin-top: 20px;
    }
    .pipeline-status-success {
        color: #27ae60;
        font-weight: bold;
    }
    .pipeline-status-pending {
        color: #e67e22;
        font-weight: bold;
    }
    .pipeline-status-failed {
        color: #e74c3c;
        font-weight: bold;
    }
    .markdown-report {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    .filter-tags {
        margin-bottom: 20px;
        padding: 10px;
        background-color: #f9f9fb;
        border-radius: 8px;
    }
    .filter-tag {
        display: inline-block;
        background-color: #f1f1f1;
        color: #333;
        padding: 5px 10px;
        border-radius: 15px;
        margin-right: 10px;
        font-size: 14px;
        margin-bottom: 5px;
    }
    
    .qa-form {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    textarea.st-bq {
        border: 1px solid #e0e0e0 !important;
        border-radius: 5px !important;
        padding: 10px !important;
    }
    
    /* Custom markdown styling */
    .custom-markdown {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #e9ecef;
    }
    
    .custom-markdown pre {
        background-color: #f1f3f5;
        padding: 10px;
        border-radius: 4px;
        overflow-x: auto;
    }
    
    .custom-markdown code {
        color: #e83e8c;
        font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    
    .submit-button {
        background-color: #2ecc71;
        color: white;
        font-weight: bold;
        padding: 10px 16px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    
    .submit-button:hover {
        background-color: #27ae60;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def api_request(data=None):
    """Make a request to the consolidated FastAPI endpoint"""
    url = f"{API_URL}/jobs-api"
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def get_jobs(role=None, time_filter=None, seniority_level=None, employment_type=None):
    """Get job listings from the API with optional filtering"""
    response = api_request({
        "filter": {
            "role": role,
            "time_filter": time_filter,
            "seniority_level": seniority_level,
            "employment_type": employment_type,
            "action": "filter"
        }
    })
    
    if response and "jobs" in response:
     
        jobs_df = pd.DataFrame(response["jobs"])
        
       
        if not jobs_df.empty and "POSTED_DATE" in jobs_df.columns:
            jobs_df["POSTED_DATE"] = pd.to_datetime(jobs_df["POSTED_DATE"])
            
        return jobs_df
    
    return pd.DataFrame(columns=["POSTED_DATE", "JOB_ROLE", "TITLE", "COMPANY", "SENIORITY_LEVEL", "EMPLOYMENT_TYPE", "SKILLS", "URL"])

def request_interview_prep(job_role, skills, job_url, user_email=""):
    """Request interview preparation materials"""
    
    interview_prep_data = {
        "skills": skills,
        "job_url": job_url,
        "user_email": user_email
    }
    
    response = api_request({
        "filter": {
            "action": "interview-prep"
        },
        "interview_prep": {
            "job_role": job_role,
            "skills": skills,
            "job_url": job_url
        }
    })
    
    return response

def fetch_pipeline_runs():
    """Fetch all pipeline runs"""
    response = api_request({
        "filter": {
            "action": "qa-pipeline"
        },
        "qa_pipeline": {
            "action": "get_pipeline_runs"
        }
    })
    
    if response and response.get("status") == "success":
        return response.get("pipeline_runs", [])
    
    return []

def fetch_pipeline_status(dag_run_id):
    """Fetch the status of a specific pipeline run"""
    response = api_request({
        "filter": {
            "action": "qa-pipeline"
        },
        "qa_pipeline": {
            "action": "get_status",
            "dag_run_id": dag_run_id
        }
    })
    
    if response and response.get("status") == "success":
        return response.get("pipeline_status")
    
    return None

def fetch_qa_questions(dag_run_id):
    """Fetch QA questions for a specific pipeline run"""
    response = api_request({
        "filter": {
            "action": "qa-pipeline"
        },
        "qa_pipeline": {
            "action": "get_questions",
            "dag_run_id": dag_run_id
        }
    })
    
    if response and response.get("status") == "success":
        return response.get("questions")
    
    return None

def submit_qa_answers(dag_run_id, answers):
    """Submit answers to QA questions"""
   
    response = api_request({
        "filter": {
            "action": "qa-pipeline"
        },
        "qa_pipeline": {
            "action": "submit_answers",
            "dag_run_id": dag_run_id,
            "answers": answers
        }
    })
    
    return response

def fetch_qa_report(dag_run_id):
    """Fetch QA report for a specific pipeline run"""
    response = api_request({
        "filter": {
            "action": "qa-pipeline"
        },
        "qa_pipeline": {
            "action": "get_report",
            "dag_run_id": dag_run_id
        }
    })
    
    if response and response.get("status") == "success":
        return response.get("report")
    
    return None

def fetch_cache_status():
    """Fetch cache status from the API"""
    return api_request({
        "filter": {
            "action": "status"
        }
    })

def refresh_cache():
    """Manually refresh the cache"""
    with st.spinner("Refreshing job data..."):
        response = api_request({
            "filter": {
                "action": "refresh"
            }
        })
        if response and response.get("status") == "success":
            st.success("Job data refreshed successfully!")
            return True
        else:
            st.error("Failed to refresh job data.")
            return False

def export_jobs_as_csv(role=None, time_filter=None, seniority_level=None, employment_type=None):
    """Export job listings as CSV"""
    response = api_request({
        "filter": {
            "role": role,
            "time_filter": time_filter,
            "seniority_level": seniority_level,
            "employment_type": employment_type,
            "action": "export"
        }
    })
    
    if response and "csv_data" in response:
        return response["csv_data"]
    
    return None

def format_datetime(dt):
    """Format datetime for display"""
    if pd.isnull(dt):
        return "N/A"
    
    now = datetime.datetime.now()
    delta = now - dt
    
    if delta.days == 0:
        if delta.seconds < 60:
            return "Just now"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days < 7:
        return f"{delta.days} days ago"
    else:
        return dt.strftime("%b %d, %Y")

def parse_skills(skills_str):
    """Parse skills string into a list"""
    if pd.isna(skills_str) or not skills_str:
        return []
    
    try:
        # Try to parse as JSON if it's in JSON format
        return json.loads(skills_str)
    except:
        # Otherwise, split by commas
        return [skill.strip() for skill in skills_str.split(",") if skill.strip()]

# Initialize session state
if 'first_load' not in st.session_state:
    st.session_state.first_load = True
    st.session_state.jobs_data = None
    st.session_state.selected_role = "All Roles"
    st.session_state.selected_time = "All Time"
    st.session_state.selected_seniority = "All Levels"
    st.session_state.selected_employment = "All Types"
    st.session_state.filters_applied = False
    st.session_state.filter_pending = False
    st.session_state.interview_prep_job = None
    st.session_state.page = "job_listings"  # Default page
    st.session_state.current_dag_run_id = None
    st.session_state.qa_answers = {}
    st.session_state.qa_report = None
    st.session_state.report_loading = False

# Job Listings Page
def job_listings_page():
    # App header with better styling
    st.markdown("<h1 class='app-header'>🔍 Latest Job Listings</h1>", unsafe_allow_html=True)
    st.markdown("<p class='app-subtitle'>Find the latest job openings matching your skills and preferences</p>", unsafe_allow_html=True)
    
 
    
    # Cache status display in sidebar
    st.sidebar.title("Job Data Cache")
    cache_status = fetch_cache_status()
    
    if cache_status:
        last_refresh = "Never"
        if cache_status.get("last_refresh"):
            try:
                last_refresh_time = datetime.datetime.fromisoformat(cache_status["last_refresh"])
                last_refresh = format_datetime(last_refresh_time)
            except:
                last_refresh = cache_status["last_refresh"]
        
        if "cache_exists" in cache_status and cache_status["cache_exists"]:
            job_count = cache_status.get("job_count", 0)
            st.sidebar.success(f"✅ Cache Status: Active\n\nLast Refresh: {last_refresh}\n\nCached Jobs: {job_count}")
        else:
            st.sidebar.warning("⚠️ Cache not initialized")
        
        # Manual refresh button
        if st.sidebar.button("🔄 Refresh Job Data", key="refresh_cache"):
            if refresh_cache():
                st.session_state.jobs_data = None
                st.session_state.first_load = True
                st.session_state.filters_applied = False
                st.experimental_rerun()
    
    # Sidebar filters
    st.sidebar.title("Filter Options")
    
    # Role filter - Dropdown with fixed options
    role_options = ["All Roles", "data_engineer", "data_scientist", "software_engineer"]
    selected_role = st.sidebar.selectbox(
        "Job Role",
        role_options,
        index=role_options.index(st.session_state.selected_role) if st.session_state.selected_role in role_options else 0,
    )
    
    # Seniority level filter
    seniority_options = [
        "All Levels", "Entry level", "Associate", "Internship", 
        "Mid-Senior level", "Director", "Not Applicable"
    ]
    selected_seniority = st.sidebar.selectbox(
        "Seniority Level",
        seniority_options,
        index=seniority_options.index(st.session_state.selected_seniority) if st.session_state.selected_seniority in seniority_options else 0,
    )
    
    # Employment type filter
    employment_options = ["All Types", "Full-time", "Part-time", "Contract"]
    selected_employment = st.sidebar.selectbox(
        "Employment Type",
        employment_options,
        index=employment_options.index(st.session_state.selected_employment) if st.session_state.selected_employment in employment_options else 0,
    )
    
    # Time filter
    time_options = [
        "All Time",
        "Last 30 minutes", 
        "Last hour", 
        "Last 2 hours", 
        "Last 3 hours",
        "Last 4 hours"
    ]
    selected_time = st.sidebar.selectbox(
        "Posted Within",
        time_options,
        index=time_options.index(st.session_state.selected_time) if st.session_state.selected_time in time_options else 0,
    )
    
    # Apply filters button - Only trigger filtering when this button is clicked
    filters_changed = (
        selected_role != st.session_state.selected_role or
        selected_time != st.session_state.selected_time or
        selected_seniority != st.session_state.selected_seniority or
        selected_employment != st.session_state.selected_employment
    )
    
    if filters_changed:
        st.session_state.filter_pending = True
    
    # Only apply filters when the button is clicked
    if st.sidebar.button("Apply Filters", key="apply_filters") or st.session_state.filters_applied == False:
        st.session_state.selected_role = selected_role
        st.session_state.selected_time = selected_time
        st.session_state.selected_seniority = selected_seniority
        st.session_state.selected_employment = selected_employment
        st.session_state.filters_applied = True
        st.session_state.filter_pending = False
    
    # Reset filters button
    if st.sidebar.button("Reset Filters", key="reset_filters"):
        st.session_state.selected_role = "All Roles"
        st.session_state.selected_time = "All Time"
        st.session_state.selected_seniority = "All Levels"
        st.session_state.selected_employment = "All Types"
        st.session_state.filters_applied = True
        st.session_state.filter_pending = False
        st.experimental_rerun()
    
    # Export button
    export_button = st.sidebar.button("📊 Export Filtered Data", key="export_csv")
    
    # Show pending filter changes notification
    if st.session_state.filter_pending:
        st.sidebar.warning("⚠️ Filter changes not applied yet. Click 'Apply Filters' to update results.")
    
    # Convert UI filters to API parameters for display and filtering
    api_role = None if st.session_state.selected_role == "All Roles" else st.session_state.selected_role
    api_seniority = None if st.session_state.selected_seniority == "All Levels" else st.session_state.selected_seniority
    api_employment = None if st.session_state.selected_employment == "All Types" else st.session_state.selected_employment
    
    api_time = None
    if st.session_state.selected_time == "Last 30 minutes":
        api_time = "30min"
    elif st.session_state.selected_time == "Last hour":
        api_time = "1hr"
    elif st.session_state.selected_time == "Last 2 hours":
        api_time = "2hr" 
    elif st.session_state.selected_time == "Last 3 hours":
        api_time = "3hr"
    elif st.session_state.selected_time == "Last 4 hours":
        api_time = "4hr"
    
    # Load jobs data on first load
    if st.session_state.first_load or st.session_state.jobs_data is None:
        with st.spinner("Loading job listings..."):
            all_jobs_df = get_jobs()
            if all_jobs_df is not None and not all_jobs_df.empty:
                st.session_state.jobs_data = all_jobs_df
                st.session_state.first_load = False
            else:
                st.warning("Failed to load job listings. Please try refreshing the page.")
    
    # Apply filters to the DataFrame in memory (no new API call)
    jobs_df = None
    if st.session_state.jobs_data is not None:
        jobs_df = st.session_state.jobs_data.copy()
        
        # Apply role filter
        if api_role:
            jobs_df = jobs_df[jobs_df["JOB_ROLE"] == api_role]
        
        # Apply seniority filter
        if api_seniority:
            # Handle null/NaN values
            if "SENIORITY_LEVEL" in jobs_df.columns:
                jobs_df = jobs_df[jobs_df["SENIORITY_LEVEL"].fillna("Not Applicable") == api_seniority]
        
        # Apply employment type filter
        if api_employment:
            # Handle null/NaN values
            if "EMPLOYMENT_TYPE" in jobs_df.columns:
                jobs_df = jobs_df[jobs_df["EMPLOYMENT_TYPE"].fillna("Not Applicable") == api_employment]
        
        # Apply time filter
        if api_time:
            hours_map = {
                "30min": 0.5,
                "1hr": 1,
                "2hr": 2,
                "3hr": 3,
                "4hr": 4
            }
            hours = hours_map.get(api_time, 0)
            if hours > 0:
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
                jobs_df = jobs_df[jobs_df["POSTED_DATE"] >= cutoff_time]
        
        # Handle CSV export request
        if export_button and jobs_df is not None:
            csv_data = export_jobs_as_csv(
                role=api_role,
                time_filter=api_time,
                seniority_level=api_seniority,
                employment_type=api_employment
            )
            if csv_data:
                st.sidebar.download_button(
                    label="⬇️ Download CSV File",
                    data=csv_data,
                    file_name=f"job_listings_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
                st.sidebar.success("CSV file ready for download!")
            else:
                st.sidebar.error("Failed to generate CSV file. Please try again.")
                
        # Show applied filters as tags
        filter_tags = []
        if api_role:
            filter_tags.append(f"Role: {api_role}")
        if api_seniority:
            filter_tags.append(f"Level: {api_seniority}")
        if api_employment:
            filter_tags.append(f"Type: {api_employment}")
        if api_time:
            filter_tags.append(f"Time: {st.session_state.selected_time}")
            
        if filter_tags:
            filter_html = "<div class='filter-tags'><strong>Active Filters:</strong> " + " ".join([f"<span class='filter-tag'>{tag}</span>" for tag in filter_tags]) + "</div>"
            st.markdown(filter_html, unsafe_allow_html=True)
        
        # Show job count
        if jobs_df.empty:
            st.warning("No job listings found matching your criteria.")
        else:
            st.write(f"Found **{len(jobs_df)}** job listings")
            
            # Display jobs in a visually appealing way using unified cards
            for idx, job in jobs_df.iterrows():
                # Get job details with fallbacks for missing data
                job_title = job.get('TITLE') if pd.notna(job.get('TITLE')) else job.get('JOB_ROLE', 'Unknown Position')
                job_company = job.get('COMPANY') if pd.notna(job.get('COMPANY')) else 'Unknown Company'
                job_location = job.get('LOCATION') if pd.notna(job.get('LOCATION')) else 'United States'
                job_role = job.get('JOB_ROLE', '')
                job_url = job.get('URL', '#')
                job_seniority = job.get('SENIORITY_LEVEL') if pd.notna(job.get('SENIORITY_LEVEL')) else 'Not Specified'
                job_employment = job.get('EMPLOYMENT_TYPE') if pd.notna(job.get('EMPLOYMENT_TYPE')) else 'Not Specified'
                posted_date = format_datetime(job.get('POSTED_DATE')) if pd.notna(job.get('POSTED_DATE')) else 'Unknown'
                
                # Parse skills
                skills_str = job.get('SKILLS')
                skills = parse_skills(skills_str)
                
                # Create a unique key for this job
                job_key = f"job-{idx}"
                
                # Create job card
                with st.container():
                    job_card = f"""
                    <div class="job-card">
                        <div class="job-title">{job_title}</div>
                        <div class="job-company">{job_company}</div>
                        <div class="job-meta">
                            <span class="job-role-tag">{job_role}</span>
                            <span style="margin-left: 10px;">{job_seniority}</span>
                            <span style="margin-left: 10px;">{job_employment}</span>
                            <span style="margin-left: 10px;">{job_location}</span>
                        </div>
                        <div class="job-date">Posted: {posted_date}</div>
                        <div class="job-buttons">
                            <a href="{job_url}" target="_blank" class="view-button">View Job Listing</a>
                            </a>
                        </div>
                    """
                    
                    # Add skills if any
                    if skills:
                        job_card += "<div class='skills-title'>🔧 Skills</div>"
                        skills_html = "".join([f"<span class='skill-tag'>{skill}</span>" for skill in skills])
                        job_card += skills_html
                    else:
                        job_card += "<div class='skills-title'>🔧 Skills</div><em>No skills listed</em>"

                    job_card += "</div>"

                    st.markdown(job_card, unsafe_allow_html=True)
                    
                    # Hidden button for interview prep
                    if st.button("Prepare for Interview", key=f"prep-{job_key}", help="Prepare for this job interview", type="secondary"):
                        with st.spinner("Setting up interview preparation..."):
                            # Convert skills to a list if it's not already
                            skill_list = skills if isinstance(skills, list) else parse_skills(skills_str)
                            
                            # Submit interview prep request with user email
                            response = request_interview_prep(job_role, skill_list, job_url, st.session_state.user_email)
                            
                            if response and response.get("status") == "success":
                                st.success("Interview preparation set up successfully!")
                                st.info("Go to the QA tab to view your interview questions.")
                                
                                # Simple button to go to QA tab
                                if st.button("Go to QA Tab", key=f"goto_qa_{job_key}"):
                                    st.session_state.page = "qa"
                                    st.experimental_rerun()
                            else:
                                st.error("Failed to set up interview preparation. Please try again.")
                    
                    st.markdown("<hr style='margin: 30px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

job_listings_page()


# # Main app
# def main():
#     # Add a navigation option to switch between Job Listings and QA
#     st.sidebar.title("Navigation")
#     page = st.sidebar.radio("Select Page:", ["Job Listings", "QA"])
    
#     if page == "Job Listings":
#         st.session_state.page = "job_listings"
#     else:
#         st.session_state.page = "qa"
    
#     # Render the selected page
#     if st.session_state.page == "job_listings":
#         job_listings_page()
#     else:
#         qa_page()

# if __name__ == "__main__":
#     main()