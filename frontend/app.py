import streamlit as st
import os
import json
import requests
import copy
import re
import time
import threading
from pathlib import Path
from static import helper
import logging
import pandas as pd
import datetime
import base64
from qa import qa_page


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

API_URL ="https://botfolio-apis-548112246073.us-central1.run.app"
# API_URL = "http://127.0.0.1:8000"

# Set up the correct path to your images
PREVIEW_DIR = Path(__file__).parent.parent / "static" / "images"
os.makedirs(PREVIEW_DIR, exist_ok=True)

# Cache for API responses to reduce redundant API calls
CACHE = {}
# -----------------
# HELPER FUNCTIONS
# -----------------
def run_async(func, callback=None):
    """Run a function asynchronously with improved error handling and UI stability"""
    def wrapper():
        try:
            result = func()
            # Use streamlit's queue system for callback to prevent UI flicker
            if callback:
                st.session_state.async_callback_result = result
                st.session_state.async_callback_ready = True
        except Exception as e:
            logging.error(f"Async error: {str(e)}")
            st.session_state.async_error = str(e)
            if callback:
                st.session_state.async_callback_result = None
                st.session_state.async_callback_ready = True
    
    thread = threading.Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    
    # Check if we need to process a callback
    if "async_callback_ready" in st.session_state and st.session_state.async_callback_ready:
        callback(st.session_state.async_callback_result)
        st.session_state.async_callback_ready = False
        del st.session_state.async_callback_result
    
    return thread

class APIClient:
    """Class to handle API requests with caching and auth"""
    
    @staticmethod
    def request(endpoint, method="get", headers=None, data=None, files=None, params=None, use_cache=True):
        """Make API requests to the backend with proper error handling and caching"""
        url = f"{API_URL}/{endpoint}"
        headers = headers or {}
        cache_key = None
        
        # Add auth token if available
        if "Authorization" not in headers and "token" in st.session_state:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        
        # Check cache for GET requests
        if method.lower() == "get" and use_cache:
            cache_key = f"{url}_{str(params)}"
            if cache_key in CACHE:
                return CACHE[cache_key]
        
        try:
            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=params)
            elif method.lower() == "post":
                # If files are included, don't use json=data
                if files:
                    response = requests.post(url, headers=headers, files=files, data=data)
                else:
                    response = requests.post(url, headers=headers, json=data)
            elif method.lower() == "put":
                response = requests.put(url, headers=headers, json=data)
            elif method.lower() == "delete":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Handle API errors
            if response.status_code >= 400:
                error_detail = "Unknown error"
                try:
                    error_detail = response.json().get("detail", error_detail)
                except:
                    pass
                raise Exception(f"API Error ({response.status_code}): {error_detail}")
            
            result = response.json()
            
            # Cache successful GET responses
            if method.lower() == "get" and use_cache and cache_key:
                CACHE[cache_key] = result
            
            return result
        except requests.RequestException as e:
            st.error(f"API Connection Error: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None

# -----------------
# AUTH FUNCTIONS
# -----------------
def login(email, password):
    """Login user and get token"""
    response = APIClient.request("login", method="post", data={"user_email": email, "password": password})
    
    if response:
        # Check for error status code
        if "status_code" in response and response["status_code"] == 401:
            # st.error(response.get("message", "Login failed"))
            return False
            
        # Store user session data
        st.session_state.user_email = email
        st.session_state.is_authenticated = True
        
        # Set user data from response
        if "user_data" in response and response["user_data"]:
            user_data = response["user_data"]
            st.session_state.user_name = user_data["NAME"]
            
            if user_data["UI_ENDPOINT"] == "null":
                st.session_state.is_site_hosted = False
            else:
                st.session_state.is_site_hosted = user_data["UI_ENDPOINT"]
                
            if user_data["UI_ENDPOINT"]:
                st.session_state.site_url = user_data["UI_ENDPOINT"]
                st.session_state.repo_name = user_data["UI_ENDPOINT"].split("/")[-2]
                st.session_state.selected_theme = user_data["THEME"]
                st.session_state.theme_selected = True
                resume_data = json.loads(user_data["RESUME_JSON"])
                st.session_state.resume_data = resume_data
                st.session_state.edited_resume = copy.deepcopy(resume_data)
                
            # Reset messages for returning users
            if "messages" in st.session_state:
                del st.session_state.messages
                
            return True
        else:
            st.error("Invalid response format from server")
            return False
    
    return False

def register(email, password):
    """Register a new user"""
    response = APIClient.request("register", method="post", data={"email": email, "password": password})
    if response:
        st.session_state.user_email = email
        st.session_state.is_authenticated = True
        st.session_state.is_site_hosted = 0
        return True
    return False

def contains_special_characters(s):
    # This pattern matches any character that is NOT a-z, A-Z, 0-9, or space
    return bool(re.search(r'[^a-zA-Z0-9 ]', s))

def validate_repo_name(repo_name):
    """Check if repository name is available"""
    # Cache validation results to prevent repeated calls
    cache_key = f"validate_repo_{repo_name}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    if contains_special_characters(repo_name):
        return False
    response = APIClient.request("validate-repo", method="post", data={"repo_name": repo_name})
    if response:
        valid = response["valid"]
        st.session_state[cache_key] = valid
        return valid
    return False

def deploy_portfolio(user_email, theme, repo_name, callback=None):
    """Deploy portfolio to GitHub asynchronously with improved state management"""
    
    # Set deployment state before starting
    if "deployment_started" not in st.session_state:
        st.session_state.deployment_started = True
        st.session_state.deployment_completed = False
    
    def deploy_task():
        try:
            # Add a small delay before starting to ensure UI is rendered properly
            time.sleep(0.2)
            
            response = APIClient.request("deploy", method="post", data={
                "repo_name": repo_name,
                "theme": theme,
                "user_email": user_email
            })
        
            if response and "url" in response:
                url = response["url"]
                # Update session state directly instead of relying solely on callback
                st.session_state.deployment_url = url
                st.session_state.deployment_completed = True
                st.session_state.deployment_complete = True
                st.session_state.is_site_hosted = 1
                st.session_state.site_url = url
                
                if callback:
                    callback(url)  # Call the callback with the URL on success
                return url
            else:
                st.session_state.deployment_error = True
                if callback:
                    callback(None)  # Call callback with None if no valid response
                return None
        
        except Exception as e:
            logging.error(f"Error in deploy task: {str(e)}")
            st.session_state.deployment_error = True
            st.session_state.deployment_error_message = str(e)
            if callback:
                callback(None)
            return None
        
    # Start deployment in background thread
    run_async(deploy_task, callback)

def handle_deployment_completion(url):
    """Callback for when deployment completes"""
    if url:
        st.session_state.deployment_url = url
        st.session_state.is_site_hosted = 1
        st.session_state.site_url = url
        st.session_state.deployment_complete = True
        st.session_state.deployment_completed = True

def update_resume(resume_data):
    """Update resume data in the backend"""
    response = APIClient.request("update-resume", method="put", data={
        "resume_data": resume_data,
        "user_email": st.session_state.user_email  # Added user_email to ensure correct user data is updated
    })
    # Return True if successful, False otherwise
    return response is not None

def save_resume_changes():
    """Save resume changes to backend - call this before deployment"""
    if "edited_resume" in st.session_state and "resume_data" in st.session_state:
        # Check if there are actual changes to save
        if st.session_state.edited_resume != st.session_state.resume_data:
            # with st.spinner("Saving resume changes..."):
                try:
                    # Use the same endpoint that's working for the chatbot
                    response = requests.post(
                        f"{API_URL}/json-to-sf", 
                        json={
                            "user_email": st.session_state.user_email,
                            "mode": "update",  # Use a mode that signals this is a direct save
                            "resume_data": st.session_state.edited_resume
                        }
                    )
                    
                    if response.status_code >= 400:
                        st.error(f"Error saving changes")
                        return False
                    else:         
                        # Update local copy to match what was saved
                        st.session_state.edited_resume = response.json().get("data", {})
                        st.session_state.resume_data = copy.deepcopy(st.session_state.edited_resume)
                        logging.info("Resume changes saved successfully")
                        return True
                except Exception as e:
                    st.error(f"Error saving changes: {str(e)}")
                    return False
        else:
            logging.info("No changes to save - resume data is already up to date")
            return True  # No changes needed
    return False  # No resume data to save

# -----------------
# UI COMPONENTS
# -----------------

def display_theme_selector(themes):
    """Display theme selection cards with static image previews"""
    st.subheader("Choose a Theme")

    cols = st.columns(2)
    
    for i, theme_name in enumerate(themes.keys()):
        col = cols[i % 2]
        with col:
            st.markdown(f"### {theme_name}")
            st.markdown(f"*{themes[theme_name]['description']}*")

            # Preview image - cache check to avoid file I/O on every rerun
            image_path_key = f"image_path_{theme_name}"
            if image_path_key not in st.session_state:
                image_found = False
                for ext in ['png', 'jpg', 'jpeg']:
                    preview_path = PREVIEW_DIR / f"{theme_name.lower().replace(' ', '_')}_preview.{ext}"
                    if preview_path.exists():
                        st.session_state[image_path_key] = str(preview_path)
                        image_found = True
                        break
                
                if not image_found:
                    st.session_state[image_path_key] = f"https://via.placeholder.com/600x400?text={theme_name}+Preview"

            col.image(st.session_state[image_path_key], 
                      caption=f"Preview of {theme_name}", 
                      use_container_width=True)
            
            # Theme selection button
            if col.button(f"Select {theme_name}", key=f"select_button_{theme_name}"):
                st.session_state.selected_theme = theme_name
                st.session_state.theme_selected = True
                st.success(f"✅ You selected **{theme_name}**.")
                return

def display_resume_json(resume_data):
    import hashlib
    import json
    
    if resume_data:
        current_hash = hashlib.md5(json.dumps(resume_data, sort_keys=True).encode()).hexdigest()
    else:
        current_hash = "none"
    
    # Initialize preview state
    if "preview_hash" not in st.session_state:
        st.session_state.preview_hash = None
        st.session_state.preview_key = 0
    
    # Only increment key when resume data changes
    if st.session_state.preview_hash != current_hash:
        st.session_state.preview_key += 1
        st.session_state.preview_hash = current_hash
    
    # Use the key to force container recreation only when data changes
    with st.container(key=f"preview_container_{st.session_state.preview_key}"):
        # About section
        if "about" in resume_data:
            about = resume_data["about"]
            st.subheader("📋 Personal Information")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Name:** {about.get('name', 'Not specified')}")
                st.markdown(f"**Email:** {about.get('email', 'Not specified')}")
                st.markdown(f"**Phone:** {about.get('phone', 'Not specified')}")
            with col2:
                st.markdown(f"**Location:** {about.get('location', 'Not specified')}")
                st.markdown(f"**LinkedIn:** {about.get('linkedin_hyperlink', 'Not specified')}")
                st.markdown(f"**GitHub:** {about.get('github_hyperlink', 'Not specified')}")
            
            if "summary" in about:
                st.markdown(f"**Summary:** {about['summary']}")
            
            st.markdown("---")
        
        # Education section
        if "education" in resume_data and resume_data["education"]:
            st.subheader("🎓 Education")
            for i, edu in enumerate(resume_data["education"]):
                with st.expander(f"{edu.get('university', 'University')} - {edu.get('degree', 'Degree')}"):
                    st.markdown(f"**University:** {edu.get('university', 'Not specified')}")
                    st.markdown(f"**Location:** {edu.get('location', 'Not specified')}")
                    st.markdown(f"**Degree:** {edu.get('degree', 'Not specified')}")
                    st.markdown(f"**Period:** {edu.get('period', 'Not specified')}")
                    
                    if "gpa" in edu:
                        st.markdown(f"**GPA:** {edu['gpa']}")
                    
                    if "related_coursework" in edu and edu["related_coursework"]:
                        st.markdown("**Related Coursework:**")
                        for course in edu["related_coursework"]:
                            st.markdown(f"- {course}")
            
            st.markdown("---")
        
        # Skills section
        if "skills" in resume_data and resume_data["skills"]:
            st.subheader("🔧 Skills")
            for skill_group in resume_data["skills"]:
                with st.expander(skill_group.get("category", "Skills")):
                    if "skills" in skill_group and skill_group["skills"]:
                        st.markdown(", ".join(skill_group["skills"]))
            
            st.markdown("---")
        
        # Experience section
        if "experience" in resume_data and resume_data["experience"]:
            st.subheader("💼 Work Experience")
            for i, exp in enumerate(resume_data["experience"]):
                with st.expander(f"{exp.get('position', 'Position')} at {exp.get('company', 'Company')}"):
                    st.markdown(f"**Company:** {exp.get('company', 'Not specified')}")
                    st.markdown(f"**Position:** {exp.get('position', 'Not specified')}")
                    st.markdown(f"**Period:** {exp.get('period', 'Not specified')}")
                    st.markdown(f"**Location:** {exp.get('location', 'Not specified')}")
                    
                    if "responsibilities" in exp and exp["responsibilities"]:
                        st.markdown("**Responsibilities:**")
                        for resp in exp["responsibilities"]:
                            st.markdown(f"- {resp}")
            
            st.markdown("---")
        
        # Projects section
        if "projects" in resume_data and resume_data["projects"]:
            st.subheader("🚀 Projects")
            for i, proj in enumerate(resume_data["projects"]):
                with st.expander(proj.get("name", "Project")):
                    st.markdown(f"**Name:** {proj.get('name', 'Not specified')}")
                    st.markdown(f"**Description:** {proj.get('description', 'Not specified')}")
                    
                    if "url" in proj and proj["url"]:
                        st.markdown(f"**URL:** {proj['url']}")
                    
                    if "technologies" in proj and proj["technologies"]:
                        st.markdown("**Technologies:**")
                        st.markdown(", ".join(proj["technologies"]))
            
            st.markdown("---")
        
        # Accomplishments section
        if "accomplishments" in resume_data and resume_data["accomplishments"]:
            st.subheader("🏆 Accomplishments")
            for i, accom in enumerate(resume_data["accomplishments"]):
                with st.expander(accom.get("title", "Accomplishment")):
                    st.markdown(f"**Title:** {accom.get('title', 'Not specified')}")
                    st.markdown(f"**Date:** {accom.get('date', 'Not specified')}")
                    
                    if "link" in accom and accom["link"]:
                        st.markdown(f"**Link:** {accom['link']}")
            
            st.markdown("---")

def create_llm_based_editor(resume_data):
    """Create an LLM-based chat editor for resume data with improved UI stability"""
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I'm your AI resume editor. Please tell me what changes you'd like to make to your resume. You can say things like:\n\n- Update my job title at Google to 'Senior Software Engineer'\n- Add a new project called 'Portfolio Generator'\n- Update my skills to include 'React', 'Node.js', and 'Python'\n- Add a new work experience"}
        ]
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # User input
    if prompt := st.chat_input("What would you like to edit in your resume?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Set a processing flag to prevent multiple UI updates
        # if "llm_processing" not in st.session_state:
        #     st.session_state.llm_processing = True
            
            # Show a spinner message without blocking
            with st.status("Updating your resume...", expanded=True) as status:
                try:
                    # Call the API endpoint
                    response = requests.post(
                        f"{API_URL}/json-to-sf", 
                        json={"changes": prompt, "mode": "revise", "user_email": st.session_state.user_email}
                    )
                    
                    # Process response
                    if response.status_code == 200:
                        # Extract the JSON and update session state
                        updated_resume = response.json().get("data", {})
                        st.session_state.edited_resume = updated_resume
                        st.session_state.resume_updated = True
                        
                        # Force refresh the preview by changing last_displayed_resume
                        if "last_displayed_resume" in st.session_state:
                            del st.session_state.last_displayed_resume
                        
                        # Prepare assistant response
                        assistant_response = "✅ I've updated your resume! Here's what changed:\n\n"
                        
                        # Identify the changes (simplified version)
                        if "about" in prompt.lower():
                            assistant_response += "- Updated your personal information\n"
                        if "education" in prompt.lower() or "university" in prompt.lower() or "degree" in prompt.lower():
                            assistant_response += "- Updated your education details\n"
                        if "skill" in prompt.lower():
                            assistant_response += "- Updated your skills\n"
                        if "experience" in prompt.lower() or "job" in prompt.lower() or "work" in prompt.lower():
                            assistant_response += "- Updated your work experience\n"
                        if "project" in prompt.lower():
                            assistant_response += "- Updated your projects\n"
                        if "accomplishment" in prompt.lower() or "award" in prompt.lower() or "certification" in prompt.lower():
                            assistant_response += "- Updated your accomplishments\n"
                        
                        assistant_response += "\nYou can see the changes in the resume preview. Is there anything else you'd like to update?"
                        status.update(label="Resume updated successfully!", state="complete")
                        # st.rerun()
                    else:
                        # Handle error
                        status.update(label=f"Error updating resume: {response.text}", state="error")
                        assistant_response = "I had trouble updating your resume. Please try again."
                        st.session_state.edited_resume = resume_data
                        st.session_state.resume_updated = False
                        # st.rerun()
                
                except Exception as e:
                    status.update(label=f"Error: {str(e)}", state="error")
                    assistant_response = "I encountered an error while trying to update your resume. Please try again."
                    st.session_state.edited_resume = resume_data
                    st.session_state.resume_updated = False
                
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            # Display assistant response in a separate chat message
            st.rerun()
            with st.chat_message("assistant"):
                st.write(assistant_response)

            # Clear the processing flag to allow new inputs
            st.session_state.llm_processing = False

    
    return st.session_state.edited_resume

def login_page():

    # Hide default sidebar
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🌐 Portfolio Website Builder")
    st.subheader("Login to access your portfolio")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button"):
            with st.spinner("Logging in..."):
                if login(email, password):
                    st.success("Login successful!")
                    # Use session state to trigger rerun instead of direct call
                    st.session_state.login_successful = True
                    st.rerun()
                else:
                    st.error("Invalid email or password")
                
        st.markdown("---")
        st.markdown("### Register New Account")
        reg_email = st.text_input("Email", key="register_email")
        reg_password = st.text_input("Password", type="password", key="register_password")
        
        if st.button("Register", key="register_button"):
            with st.spinner("Registering..."):
                if register(reg_email, reg_password):
                    st.success("Registration successful! You're now logged in.")
                    # Use session state to trigger rerun instead of direct call
                    st.session_state.registration_successful = True
                    st.rerun()
                else:
                    st.error("Registration failed. Please try again.")
    
    with col2:
        st.markdown("### Welcome to Portfolio Website Builder")
        st.markdown("Turn your resume into a professional portfolio website in minutes!")
        
        # Add a quick description of the app
        st.markdown("""
        ### 📝 Resume to Portfolio Website Generator
        
        1. Upload your resume or enter your information
        2. Choose from beautiful portfolio themes
        3. Deploy instantly to GitHub Pages
        
        Your professional online presence is just a few clicks away!
        """)

def show_non_blocking_progress(key="progress", steps=100, time_per_step=0.40):
    """Show a progress bar without blocking the UI thread"""
    # Initialize progress state variables if they don't exist
    if f"{key}_start_time" not in st.session_state:
        st.session_state[f"{key}_start_time"] = time.time()
        st.session_state[f"{key}_total_steps"] = steps
        st.session_state[f"{key}_time_per_step"] = time_per_step
        st.session_state[f"{key}_progress"] = 0
        st.session_state[f"{key}_completed"] = False
        st.session_state[f"{key}_last_update"] = time.time()
    
    # Calculate progress based on elapsed time
    elapsed = time.time() - st.session_state[f"{key}_start_time"]
    expected_progress = min(int(elapsed / time_per_step), steps)
    
    # Always update progress to show something is happening
    st.session_state[f"{key}_progress"] = expected_progress
    
    # Display progress bar - WITHOUT key parameter
    progress_bar = st.progress(st.session_state[f"{key}_progress"] / steps)
    
    # Check if completed
    if st.session_state[f"{key}_progress"] >= steps and not st.session_state[f"{key}_completed"]:
        st.session_state[f"{key}_completed"] = True
        return True
    
    return st.session_state[f"{key}_completed"]

def handle_deployment_ui(is_new_user=False):
    """Centralized function to handle deployment UI states"""
    deployment_key = "github_deploy" if is_new_user else "deployment"
    
    # Check deployment states
    if st.session_state.get("deployment_error", False):
        st.error(f"Deployment failed: {st.session_state.get('deployment_error_message', 'Unknown error')}")
        if st.button("Try Again", key=f"retry_deploy_{deployment_key}"):
            # Reset error states
            st.session_state.deployment_error = False
            st.session_state.deployment_error_message = None
            st.session_state.deploy_clicked = False
            st.rerun()
    
    elif st.session_state.get("deployment_completed", False) or st.session_state.get("deployment_complete", False):
        # Show deployment completion UI
        url = st.session_state.get("deployment_url") or st.session_state.get("site_url")
        st.success("✅ Portfolio successfully deployed!")
        st.subheader("Your Portfolio Website")
        st.markdown(f"**Portfolio URL:** [🔗 {url}]({url})")
        st.markdown("**Note:** GitHub Pages may take a few minutes to fully activate. If the link doesn't work immediately, please wait a few minutes and try again.")
        
        # Only show balloons once
        if not st.session_state.get(f"{deployment_key}_balloons_shown", False):
            st.balloons()
            st.session_state[f"{deployment_key}_balloons_shown"] = True
            
        # Offer to go back to editing
        if st.button("← Back to Editing", key=f"back_to_edit_after_success_{deployment_key}"):
            # Make sure we preserve the edited_resume when going back to editing
            if "edited_resume" not in st.session_state and "resume_data" in st.session_state:
                st.session_state.edited_resume = copy.deepcopy(st.session_state.resume_data)
            st.session_state.show_deployment_screen = False
            st.rerun()
    
    elif st.session_state.get("show_deploy_progress", False) or st.session_state.get("show_progress", False):
        # Show non-blocking progress bar
        st.info("GitHub Pages deployment in progress...")
        completed = show_non_blocking_progress(deployment_key, 100, 0.40)
        
        # Check if deployment result is available
        if "deployment_url" in st.session_state:
            # Force state update if URL is available
            st.session_state.deployment_complete = True
            st.session_state.deployment_completed = True
            st.rerun()  # Force rerun to show completion UI
        elif completed:
            # Check if we have a URL but the states weren't updated
            if st.session_state.get("site_url"):
                st.session_state.deployment_complete = True
                st.session_state.deployment_completed = True
                st.rerun()

def deploy_existing_user_portfolio():
    """Handle deployment flow for existing users"""
    st.subheader("Deploy Changes to Your Portfolio")
    
    st.info(f"Your portfolio is currently hosted at: {st.session_state.site_url}")
    st.info(f"Repository name: {st.session_state.repo_name}")
    
    if "deploy_clicked" not in st.session_state:
        st.session_state.deploy_clicked = False
    
    if not st.session_state.deploy_clicked:
        if st.button("🚀 Update Your Portfolio", key="update_portfolio_button"):
            # Save any unsaved changes first
            with st.spinner("Saving changes before deployment..."):
                if save_resume_changes():
                    st.success("✅ Changes saved!")
                    st.session_state.last_autosave = time.time()
            
            st.session_state.deploy_clicked = True
            st.session_state.deployment_started = True
            
            # Reset deployment states
            st.session_state.deployment_complete = False
            st.session_state.deployment_completed = False
            st.session_state.deployment_error = False
            st.session_state.show_progress = True
            
            # Important: reset progress tracking
            if "deployment_start_time" in st.session_state:
                del st.session_state["deployment_start_time"]
            if "deployment_progress" in st.session_state:
                del st.session_state["deployment_progress"]
            if "deployment_completed" in st.session_state:
                del st.session_state["deployment_completed"]
            
            # Start asynchronous deployment
            deploy_portfolio(
                st.session_state.user_email,
                st.session_state.selected_theme,
                st.session_state.repo_name,
                handle_deployment_completion
            )
            
            # Display initial message
            st.info("Deployment started! This will take approximately 40 seconds...")
          
            st.rerun()
        
        # Add a button to go back to editing
        if st.button("← Back to Editing", key="back_to_edit_button"):
            # Make sure we preserve the edited_resume when going back to editing
            if "edited_resume" not in st.session_state and "resume_data" in st.session_state:
                st.session_state.edited_resume = copy.deepcopy(st.session_state.resume_data)
            st.session_state.show_deployment_screen = False
            st.rerun()
    else:
        # Force the progress bar to run for at least 10 seconds even if deployment is instant
        # Modify this section to force a minimum display time
        st.info("GitHub Pages deployment in progress...")
        
        # Get the current time
        current_time = time.time()
        
        # Initialize start time if not set
        if "deployment_start_time" not in st.session_state:
            st.session_state.deployment_start_time = current_time
            st.session_state.deployment_shown_completion = False
        
        # Calculate elapsed time
        elapsed_time = current_time - st.session_state.deployment_start_time
        
        # We want to show the progress bar for at least 10 seconds
        min_progress_time = 20.0  # seconds
        
        # Check if we have a URL but haven't shown completion long enough
        has_url = "deployment_url" in st.session_state or "site_url" in st.session_state
        
        if has_url and elapsed_time < min_progress_time:
            # Still show progress bar until min time has passed
            progress_value = min(0.95, elapsed_time / min_progress_time)
            st.progress(progress_value)
            
            # Schedule a rerun to update the progress
            time.sleep(0.1)
            st.rerun()
        
        elif has_url or elapsed_time >= min_progress_time:
            # Either we have the URL or enough time has passed
            url = st.session_state.get("deployment_url") or st.session_state.get("site_url")
            
            # Complete the progress bar
            st.progress(1.0)
            
            # Show completion message
            st.success("✅ Portfolio successfully deployed!")
            st.subheader("Your Portfolio Website")
            st.markdown(f"**Portfolio URL:** [🔗 {url}]({url})")
            st.markdown("**Note:** GitHub Pages may take a few minutes to fully activate. If the link doesn't work immediately, please wait a few minutes and try again.")
            
            # Only show balloons once
            if not st.session_state.get("deployment_balloons_shown", False):
                st.balloons()
                st.session_state.deployment_balloons_shown = True
            
            # Button to go back to editing
            if st.button("← Back to Editing", key="back_to_edit_after_deploy"):
                st.session_state.show_deployment_screen = False
                st.rerun()
        else:
            # No URL yet and still within min time, show normal progress
            progress = show_non_blocking_progress("deployment", 100, 0.40)


def deploy_new_user_portfolio(repo_name_input):
    """Handle deployment flow for new users"""
    if "deploy_clicked" not in st.session_state:
        st.session_state.deploy_clicked = False
    
    if not st.session_state.deploy_clicked:
        if st.button("🚀 Deploy to GitHub Pages", key="github_deploy_button"):
            if not repo_name_input:
                st.error("Please enter a GitHub repository name before deploying.")
            elif not st.session_state.get(f"repo_validation_{repo_name_input}", False):
                st.error("Repository name is not valid. Please choose a unique name.")
            else:
                # Save any changes first
                save_resume_changes()
                
                st.session_state.deploy_clicked = True
                st.session_state.repo_name = repo_name_input
                
                # Make sure edited_resume exists before deployment
                if "edited_resume" not in st.session_state and "resume_data" in st.session_state:
                    st.session_state.edited_resume = copy.deepcopy(st.session_state.resume_data)
                
                st.info("Deployment started! This will take approximately 40 seconds...")
                response = APIClient.request("deploy", method="post", data={
                    "repo_name": st.session_state.repo_name,
                    "theme": st.session_state.selected_theme,
                    "user_email": st.session_state.user_email
                })
                if "url" in response:
                    st.success(f"Your site has been deployed - {response.get('url')}")
                else:
                    st.error("Contact Admin, something went wrong")
    else:
        # Handle deployment UI states
        st.info('Your site has already been deployed, please visit the main page')

def render_portfolio_editor():
    # """Render the portfolio editor page"""
    
    # Determine workflow based on whether user has a hosted site
    if st.session_state.is_site_hosted:
        # For existing users with a portfolio
        tab_titles = ["1. Edit Resume"]
        tabs = st.tabs(tab_titles)
        
        with tabs[0]:  # Edit tab for existing users
            st.subheader("Edit Your Portfolio")
            
            # Make sure we reset deployment flags when entering the edit tab
            if "show_deployment_screen" not in st.session_state:
                st.session_state.show_deployment_screen = False
            
            # Only show the edit UI if we're not showing the deployment screen
            if not st.session_state.show_deployment_screen:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("Current Resume Preview")
                    display_resume_json(st.session_state.edited_resume)
                
                with col2:
                    st.subheader("AI Resume Editor")
                    create_llm_based_editor(st.session_state.edited_resume)
                
                # Auto-save changes periodically
                if "last_autosave" not in st.session_state:
                    st.session_state.last_autosave = time.time()
                
                # Only perform auto-save check if not in the middle of another operation
                if (not st.session_state.get("deploy_clicked", False) and
                    not st.session_state.get("deployment_started", False)):
                    current_time = time.time()
                    if ("edited_resume" in st.session_state and 
                        "resume_data" in st.session_state and
                        st.session_state.edited_resume != st.session_state.resume_data and
                        current_time - st.session_state.last_autosave > 60):  # Autosave every 60 seconds
                        
                        with st.spinner("Auto-saving changes..."):
                            if save_resume_changes():
                                st.success("✅ Changes auto-saved!")
                                st.session_state.last_autosave = time.time()

                col_deploy, col_save = st.columns([1, 1])
                
                with col_deploy:
                    if st.button("🚀 Deploy Your Portfolio", key="deploy_from_edit_tab"):
                        # First save any unsaved changes
                        with st.spinner("Saving changes before deployment..."):
                            if save_resume_changes():
                                st.success("✅ Changes saved!")
                                st.session_state.last_autosave = time.time()
                        
                        # Switch to deployment screen
                        st.session_state.show_deployment_screen = True
                        st.session_state.deploy_clicked = False
                        st.session_state.deployment_complete = False
                        st.session_state.show_progress = False
                        st.rerun()
            
            # Show deployment screen if the flag is set
            else:
                deploy_existing_user_portfolio()

    else:
        # For new users - full workflow
        if "active_tab" not in st.session_state:
            st.session_state.active_tab = 0
            
        tab_titles = ["1. Upload & Edit", "2. Choose Theme", "3. Preview & Deploy"]
        tabs = st.tabs(tab_titles)
        
        with tabs[0]:  # Upload & Edit tab
            resume_file = st.file_uploader("Upload Resume pdf", type=["pdf"], key="resume_uploader")
            
            if resume_file:
                # Check if we've already processed this file (to avoid re-uploading)
                file_hash = hash(resume_file.getvalue())
                process_file = True
                
                if "last_processed_file" in st.session_state and st.session_state.last_processed_file == file_hash:
                    process_file = False
                
                if process_file:
                    try:
                        with st.spinner("Processing your resume..."):
                            resume_file_obj = {"file": (resume_file.name, resume_file, "application/pdf")}
                            data = {"user_email": st.session_state.user_email}
                            
                            # Upload file to GCP
                            gcp = requests.post(f"{API_URL}/upload-to-gcp", params=data, files=resume_file_obj)
                            
                            # Generate JSON from resume
                            resume_response = requests.post(
                                f"{API_URL}/json-to-sf", 
                                json={"user_email": st.session_state.user_email, "mode": "generate"}
                            )
                            
                            if resume_response.status_code == 200:
                                resume_data = resume_response.json().get("data", {})
                                st.session_state.resume_data = resume_data
                                st.session_state.edited_resume = copy.deepcopy(resume_data)
                                st.session_state.last_processed_file = file_hash
                                st.success("Resume loaded successfully! You can now edit your information.")
                            else:
                                st.error(f"Upload a valid Resume")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                
                # Display the current resume data (read-only) and chat editor
                if "edited_resume" in st.session_state:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader("Current Resume Preview")
                        display_resume_json(st.session_state.edited_resume)
                    
                    with col2:
                        st.subheader("AI Resume Editor")
                        # LLM-based editor
                        create_llm_based_editor(st.session_state.edited_resume)
                    
                    # For new users, we still need the tab navigation but with clear deploy button
                    col_nav, col_deploy = st.columns([1, 1])
                    with col_nav:
                        if st.button("Continue to Theme Selection", key="continue_to_themes"):
                            st.session_state.active_tab = 1
                            st.success(f"✅ Step 1 completed! Please click on the '2. Choose Theme' tab to continue.")
            else:
                st.info("Please upload your resume PDF file to get started.")
             
        with tabs[1]:  # Choose Theme tab
            if st.session_state.active_tab >= 1 and "edited_resume" in st.session_state:
                # Fetch themes from API
                display_theme_selector(helper.THEMES)
                
                if st.session_state.get("theme_selected", False):
                    st.success(f"You have selected **{st.session_state.selected_theme}**")
                    if st.button("Preview & Deploy Your Portfolio", key="continue_to_deploy"):
                        st.session_state.active_tab = 2
                        st.success(f"✅ Step 2 completed! Please click on the '3. Preview & Deploy' tab to continue.")
            else:
                if st.session_state.active_tab < 1:
                    st.warning("Please complete step 1 (Upload & Edit) first.")
                else:
                    st.warning("Please upload and edit your resume first.")

        with tabs[2]:  # Preview & Deploy tab
            if st.session_state.active_tab >= 2 and "edited_resume" in st.session_state and st.session_state.get("theme_selected", False):
                st.subheader("Final Review")
                
                # Get username from the correct structure based on new JSON format
                if "about" in st.session_state.edited_resume and "name" in st.session_state.edited_resume["about"]:
                    username = st.session_state.edited_resume["about"]["name"]
                else:
                    username = "portfolio"
                    
                # Display information
                st.markdown("### Your Information")
                st.write(f"**Theme Selected**: {st.session_state.selected_theme}")
                st.write(f"**Portfolio Owner**: {username}")

                st.subheader("Repository Configuration")
                repo_name_input = st.text_input("Enter the GitHub repository name you'd like to use", key="repo_name_input")

                # Validate repo name via API - only if changed
                if repo_name_input and not st.session_state.get("deployed_clicked", False):
                    # Cache validation to prevent repeated API calls
                    validation_key = f"repo_validation_{repo_name_input}"
                    if validation_key not in st.session_state:
                        valid = validate_repo_name(repo_name_input)
                        st.session_state[validation_key] = valid
                    
                    if st.session_state[validation_key]:
                        st.success("Repository name available!")
                    else:
                        st.error(f"A repository named '{repo_name_input}' already exists or this is an invalid identifier. Please choose another name.")

                # Display deployment options
                if "deploy_clicked" not in st.session_state:
                    st.subheader("Deployment Options")
                
                # Handle deployment UI with unified function
                deploy_new_user_portfolio(repo_name_input)
                
            else:
                if st.session_state.active_tab < 2:
                    st.warning(f"Please complete steps 1-2 first before deploying.")
                elif not st.session_state.get("theme_selected", False):
                    st.warning("Please select a theme first.")
                else:
                    st.warning("Please upload your resume, edit it, and select a theme first.")


def render_sidebar():
    """Create and handle the sidebar navigation"""
    # Clear any existing sidebar elements
    st.sidebar.empty()
    
    # Create sidebar header
    st.sidebar.markdown(f"### Welcome, {st.session_state.user_name}")
    
    # If user has a hosted site, show the link
    if st.session_state.is_site_hosted:
        st.sidebar.markdown("### Your Portfolio")
        st.sidebar.markdown(f"🔗 [View your portfolio]({st.session_state.site_url})")
        st.sidebar.markdown(f"Repository: {st.session_state.repo_name}")
    
    # Add sidebar navigation menu
    st.sidebar.markdown("### Navigation")
    
    # Define available pages
    pages = {
        "Portfolio Editor": "editor",
        "Job Listings": "jobs",
        "Q&A": "qa"
    }
    
    # Create radio buttons for navigation with a unique key
    selected_page = st.sidebar.radio("Go to", list(pages.keys()), key="nav_radio")
    st.session_state.current_page = pages[selected_page]
    
    # For new users in portfolio editor mode, show progress if applicable
    if st.session_state.current_page == "editor" and not st.session_state.is_site_hosted:
        if "active_tab" in st.session_state:
            tab_titles = ["1. Upload & Edit", "2. Choose Theme", "3. Preview & Deploy"]
            current_step = st.session_state.active_tab + 1
            total_steps = 3
            st.sidebar.progress(current_step / total_steps)
            st.sidebar.write(f"**Current Progress**: Step {current_step} of {total_steps}")
            st.sidebar.write(f"**Current Step**: {tab_titles[st.session_state.active_tab]}")

            # Add next step instructions for new users
            if st.session_state.active_tab < 2:
                next_step = tab_titles[st.session_state.active_tab + 1]
                st.sidebar.info(f"**Next step**: {next_step}")
    
    # Add logout button at the bottom with a unique key
    st.sidebar.markdown("---")
    if st.sidebar.button("Logout", key="sidebar_logout_button"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    return st.session_state.current_page

    
def run_jobs_page():
    """Run the jobs page functionality without calling set_page_config"""
    try:
        # Import necessary libraries
        import datetime
        import pandas as pd
        import requests
        import json
        
        # Add CSS
        from helper import css
        st.markdown(css, unsafe_allow_html=True)
        
        # Display the header
        st.markdown("<h1 class='app-header'>🔍 Latest Job Listings</h1>", unsafe_allow_html=True)
        st.markdown("<p class='app-subtitle'>Find the latest job openings matching your skills and preferences</p>", unsafe_allow_html=True)
        
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

        def request_interview_prep(skills, job_url, user_email=""):
            """Request interview preparation materials"""
            
            interview_prep_data = {
                "skills": skills,
                "job_url": job_url,
                "user_email": user_email
            }
            
            response = requests.post(f"{API_URL}/trigger_dag", json=interview_prep_data)
            return response.json()
        
        # Define helper functions
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
                return json.loads(skills_str)
            except:
                return [skill.strip() for skill in skills_str.split(",") if skill.strip()]
        
        # Add sidebar filters
        st.sidebar.title("Filter Options")
        
        role_options = ["All Roles", "data_engineer", "data_scientist", "software_engineer"]
        selected_role = st.sidebar.selectbox(
            "Job Role",
            role_options,
            index=role_options.index(st.session_state.selected_role) if st.session_state.selected_role in role_options else 0,
        )
        
        seniority_options = [
            "All Levels", "Entry level", "Associate", "Internship", 
            "Mid-Senior level", "Director", "Not Applicable"
        ]
        selected_seniority = st.sidebar.selectbox(
            "Seniority Level",
            seniority_options,
            index=seniority_options.index(st.session_state.selected_seniority) if st.session_state.selected_seniority in seniority_options else 0,
        )
        
        employment_options = ["All Types", "Full-time", "Part-time", "Contract"]
        selected_employment = st.sidebar.selectbox(
            "Employment Type",
            employment_options,
            index=employment_options.index(st.session_state.selected_employment) if st.session_state.selected_employment in employment_options else 0,
        )
        
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
        
        filters_changed = (
            selected_role != st.session_state.selected_role or
            selected_time != st.session_state.selected_time or
            selected_seniority != st.session_state.selected_seniority or
            selected_employment != st.session_state.selected_employment
        )
        
        if filters_changed:
            st.session_state.filter_pending = True
        
        if st.sidebar.button("Apply Filters", key="apply_filters") or st.session_state.filters_applied == False:
            st.session_state.selected_role = selected_role
            st.session_state.selected_time = selected_time
            st.session_state.selected_seniority = selected_seniority
            st.session_state.selected_employment = selected_employment
            st.session_state.filters_applied = True
            st.session_state.filter_pending = False
        
        if st.sidebar.button("Reset Filters", key="reset_filters"):
            st.session_state.selected_role = "All Roles"
            st.session_state.selected_time = "All Time"
            st.session_state.selected_seniority = "All Levels"
            st.session_state.selected_employment = "All Types"
            st.session_state.filters_applied = True
            st.session_state.filter_pending = False
            st.rerun()
        
        if st.session_state.filter_pending:
            st.sidebar.warning("⚠️ Filter changes not applied yet. Click 'Apply Filters' to update results.")
        
        # Process API parameters
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
        
        # Load job listings
        if st.session_state.first_load or st.session_state.jobs_data is None:
            with st.spinner("Loading job listings..."):
                # Call API directly
                response = requests.get(f'{API_URL}/all-jobs-api')
                
                if response.status_code == 200:
                    response_json = response.json()
                    
                    # Properly handle the response structure
                    if "jobs" in response_json:
                        jobs_dict = response_json["jobs"]
                    elif "data" in response_json:
                        jobs_dict = response_json["data"]
                    else:
                        jobs_dict = []
                    
                    all_jobs_df = pd.DataFrame(jobs_dict)
                    
                    if not all_jobs_df.empty and "POSTED_DATE" in all_jobs_df.columns:
                        all_jobs_df["POSTED_DATE"] = pd.to_datetime(all_jobs_df["POSTED_DATE"])
                    
                    st.session_state.jobs_data = all_jobs_df
                    st.session_state.first_load = False
                else:
                    st.error(f"API Error: {response.status_code} for url: {API_URL}/all-jobs-api")
                    st.session_state.jobs_data = pd.DataFrame()
        
        # Display job listings
        jobs_df = None
        if st.session_state.jobs_data is not None:
            jobs_df = st.session_state.jobs_data.copy()
            
            if api_role and not jobs_df.empty and "JOB_ROLE" in jobs_df.columns:
                jobs_df = jobs_df[jobs_df["JOB_ROLE"] == api_role]
            
            if api_seniority and not jobs_df.empty and "SENIORITY_LEVEL" in jobs_df.columns:
                jobs_df = jobs_df[jobs_df["SENIORITY_LEVEL"].fillna("Not Applicable") == api_seniority]
            
            if api_employment and not jobs_df.empty and "EMPLOYMENT_TYPE" in jobs_df.columns:
                jobs_df = jobs_df[jobs_df["EMPLOYMENT_TYPE"].fillna("Not Applicable") == api_employment]
            
            if api_time and not jobs_df.empty and "POSTED_DATE" in jobs_df.columns:
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
            
            # Show job count and listings
            if jobs_df.empty:
                st.warning("No job listings found matching your criteria.")
            else:
                st.write(f"Found **{len(jobs_df)}** job listings")
                
                #here
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
                                response = request_interview_prep(skill_list, job_url, st.session_state.user_email)
                                
                                if response and response.get("status_code") == 200:
                                    st.success("Interview preparation set up successfully!")
                                    st.info("Go to the QA tab to view your interview questions.")
                                    
                                    # Simple button to go to QA tab
                                    # if st.button("Go to QA Tab", key=f"goto_qa_{job_key}"):
                                    st.session_state.page = "qa"
                                    # st.rerun()
                                else:
                                    st.error("Failed to set up interview preparation. Please try again.")
                        
                        st.markdown("<hr style='margin: 30px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)       
    except Exception as e:
        st.error(f"Error running jobs page: {str(e)}")
        import traceback
        st.code(traceback.format_exc(), language="python")


def main_app():
    """Welcome, """
    # Get the current page from sidebar navigation
    current_page = render_sidebar()
    
    # Render appropriate page based on selection
    if current_page == "editor":
        render_portfolio_editor()  # Your existing portfolio editor function
    elif current_page == "jobs":
        run_jobs_page()  # Run the jobs page functionality
    elif current_page == "qa":
        qa_page()
 


# Main app logic
def main():
    """Main entry point for the application"""
    st.set_page_config(page_title="Portfolio Builder", layout="wide")
    
    # Initialize session state for current page
    if "current_page" not in st.session_state:
        st.session_state.current_page = "editor"
    
    # Check if user is authenticated
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    
    # If not authenticated, show login page
    if not st.session_state.is_authenticated:
        login_page()
    else:
        # If authenticated, show main app with navigation
        main_app()

if __name__ == "__main__":
    main()