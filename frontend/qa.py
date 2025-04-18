import streamlit as st
import pandas as pd
import requests
import datetime
import base64
from dotenv import load_dotenv
import os
import json
import time

API_URL ="https://botfolio-apis-548112246073.us-central1.run.app"
# API_URL = "http://127.0.0.1:8000"

# QA Pipeline Status Page
def qa_page():
    st.markdown("<h1 class='app-header'>🎯 Interview Preparation</h1>", unsafe_allow_html=True)
    st.markdown("<p class='app-subtitle'>Access your interview preparation materials and practice your skills</p>", unsafe_allow_html=True)
    
    # Fetch pipeline runs
    with st.spinner("Loading interview preparation sessions..."):
        response = requests.get(f'{API_URL}/pipeline_status', params={"user_email": st.session_state.user_email}).json()
        # st.write(response)
    if 'dag_runs' in response:
        pipeline_runs = response['dag_runs']
    
    else:
        st.warning("No interview preparation sessions found. Create one by clicking 'Prepare for Interview' on a job listing.")
        pipeline_runs = []
    
    # Create a DataFrame from pipeline runs
    pipeline_df = pd.DataFrame(pipeline_runs)
    
    # Format for display
    if not pipeline_df.empty:
        display_df = pipeline_df.copy()
        
        # Add status styling
        if "STATUS" in display_df.columns:
            display_df["STATUS_DISPLAY"] = display_df["STATUS"].apply(
                lambda s: f'<span class="pipeline-status-{s.lower()}">{s.upper()}</span>'
            )
        
        # Select a pipeline run
        st.subheader("Select an Interview Preparation Session")
        
        selected_run = st.selectbox(
            "Select a session:",
            options=display_df["DAG_RUN_ID"].tolist(),
            format_func=lambda x: f"{x}"
        )
        
        st.session_state.current_dag_run_id = selected_run
        
        # Show status
        status = display_df[display_df["DAG_RUN_ID"] == selected_run]["STATUS"].iloc[0]
        st.markdown(f"Status: {display_df[display_df['DAG_RUN_ID'] == selected_run]['STATUS_DISPLAY'].iloc[0]}", unsafe_allow_html=True)
        
        # Display a refresh button for checking status
        # if st.button("Refresh Status"):
        #     current_status = fetch_pipeline_status(selected_run)
        #     if current_status:
        #         status = current_status
        #         st.markdown(f"Updated Status: <span class='pipeline-status-{status.lower()}'>{status.upper()}</span>", unsafe_allow_html=True)
        #         # Rerun to use the new status
        #         st.rerun()
        
        # If status is success, show the QA form
        if status.lower() == "success":
            # Check if we have already completed the QA session and have a report
            if st.session_state.get("qa_report"):
                st.markdown("### Interview Preparation Report")
                st.markdown("Your report has been generated. View it below or start a new interview preparation session.")
                
                # Display the report in a nicely formatted container
                st.markdown('<div class="custom-markdown">', unsafe_allow_html=True)
                st.markdown(st.session_state.qa_report, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Button to clear report and start over
                if st.button("Start New Session"):
                    st.session_state.qa_answers = {}
                    st.session_state.qa_report = None
                    st.experimental_rerun()
            else:
                # Fetch questions
                response = requests.get(f'{API_URL}/qa', params={"dag_run_id": st.session_state.current_dag_run_id}).json()
                questions_data = response.get("questions", [])
                
                if not questions_data:
                    st.warning("Questions are not available yet. Please try again later.")
                
                try:                    
                    # Display all questions with answer fields
                    display_qa_form(questions_data, st.session_state.current_dag_run_id)
                    
                except Exception as e:
                    st.error(f"Error parsing questions: {str(e)}")
        
        elif status.lower() == "pending":
            st.info("Your interview preparation is being processed. Please check back later when status shows SUCCESS.")
        else:
            st.error("Your interview preparation session failed. Please try another session.")

# Updated display_qa_form function
def display_qa_form(questions, dag_run_id):
    """Display the QA form with all questions at once, showing only the question text."""
    if not questions:
        st.warning("No questions available.")
        return

    # if st.session_state.get("report_loading"):
    #     with st.spinner("Generating your interview preparation report..."):
    #         for _ in range(6):
    #             report = fetch_qa_report(dag_run_id)
    #             if report:
    #                 st.session_state.qa_report = report
    #                 st.session_state.report_loading = False
    #                 st.experimental_rerun()
    #                 break
    #             time.sleep(5)
    #         if not st.session_state.qa_report:
    #             st.warning("Report generation is taking longer than expected. Please check back later.")
    #             st.session_state.report_loading = False
    #     return

    st.markdown("### Interview Questions")
    st.markdown("Answer the following questions to prepare for your interview. You can skip questions if needed.")

    if "qa_answers" not in st.session_state:
        st.session_state.qa_answers = {}

    with st.form("qa_form"):
        for q in questions:
            question_text = q.get("QUESTION", "")
            question_id = str(q.get("ID", ""))

            st.markdown(f'<div class="qa-question">{question_text}</div>', unsafe_allow_html=True)

            # Create a text area for each question
            st.text_area(
                label="Your Answer",
                value=st.session_state.qa_answers.get(question_id, ""),
                height=150,
                key=f"answer_{question_id}",
                label_visibility="collapsed"
            )

            st.markdown("<hr>", unsafe_allow_html=True)

        # Submit button inside the form block
        submitted = st.form_submit_button("Submit All Answers", type="primary", use_container_width=True)

    # This code executes after the form is submitted
    if submitted:
        st.success("Answers submitted successfully. Generating your report...")
        # Collect all answers from the form
        for q in questions:
            question_id = str(q.get("ID", ""))
            answer_key = f"answer_{question_id}"
              
            # Get the value from the text area
            if answer_key in st.session_state:
                # Only store non-empty answers
                if st.session_state[answer_key].strip():
                    st.session_state.qa_answers[question_id] = st.session_state[answer_key]
                else:
                    st.session_state.qa_answers[question_id] = 'Help me with this question'
        
        # Now format and display the answers
        if st.session_state.qa_answers:
            formatted_answers = [
                {"id": int(q_id), "user_answer": answer} 
                for q_id, answer in st.session_state.qa_answers.items()
            ]
            # st.write(formatted_answers)
            st.session_state.formatted_answers = formatted_answers
        else:
            st.warning("Please answer at least one question before submitting.")

        if 'formatted_answers' in st.session_state:
            with st.spinner("Submitting your answers..."):
                response = requests.post(f"{API_URL}/qa-validation", json={'answers': st.session_state.formatted_answers, 'user_email': st.session_state.user_name, 'dag_run_id': dag_run_id}).json()
                # st.write(response)
                if 'markdown' in response:
                    st.markdown(response['markdown'])
                else:
                    st.error("Failed to generate report. Please try again.")

