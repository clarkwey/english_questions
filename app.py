import streamlit as st
from logic import (
    extract_video_id, 
    fetch_transcript, 
    fetch_video_title, 
    save_project, 
    load_all_projects, 
    delete_project_file,
    check_llm_status,
    generate_questions,
    fix_flagged_questions,
    export_to_pdf
)

def init_session_state():
    """Initializes the session state for projects if it doesn't exist."""
    if 'projects' not in st.session_state:
        st.session_state.projects = load_all_projects()
    if 'current_project' not in st.session_state:
        st.session_state.current_project = None
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = False
    if 'llm_connected' not in st.session_state:
        st.session_state.llm_connected = False

def main():
    st.set_page_config(page_title="English Question Generator", page_icon="📺", layout="wide")
    init_session_state()

    # --- Top Bar: LLM Status ---
    st.session_state.llm_connected = check_llm_status()
    status_col1, status_col2 = st.columns([0.8, 0.2])
    with status_col1:
        if st.session_state.llm_connected:
            st.success("🟢 Local LLM Server: Connected (localhost:8080)")
        else:
            st.error("🔴 Local LLM Server: Disconnected (Start llama.cpp on port 8080)")
    with status_col2:
        if st.button("🔄 Check Connection", use_container_width=True):
            st.rerun()

    # --- Sidebar: Project Management ---
    st.sidebar.title("📁 Projects")
    
    # Create new project
    with st.sidebar.form("new_project_form", clear_on_submit=True):
        new_project_name = st.text_input("Create New Project", placeholder="e.g., IELTS Grammar")
        add_project_button = st.form_submit_button("Add Project")
        
        if add_project_button:
            if new_project_name and new_project_name not in st.session_state.projects:
                st.session_state.projects[new_project_name] = {"videos": []}
                st.session_state.current_project = new_project_name
                save_project(new_project_name, st.session_state.projects[new_project_name])
                st.sidebar.success(f"Project '{new_project_name}' created!")
                st.rerun()
            elif new_project_name in st.session_state.projects:
                st.sidebar.warning("Project already exists.")
            else:
                st.sidebar.error("Please enter a project name.")

    st.sidebar.divider()

    # Project Selector
    project_list = list(st.session_state.projects.keys())
    if project_list:
        try:
            current_idx = project_list.index(st.session_state.current_project)
        except ValueError:
            current_idx = 0
            st.session_state.current_project = project_list[0]

        selected_project = st.sidebar.radio(
            "Select a Project", 
            project_list, 
            index=current_idx,
            key="project_selector_radio"
        )
        
        if selected_project != st.session_state.current_project:
            st.session_state.current_project = selected_project
            st.session_state.confirm_delete = False
            st.rerun()
        
        if not st.session_state.confirm_delete:
            if st.sidebar.button("Delete Project", type="secondary"):
                st.session_state.confirm_delete = True
                st.rerun()
        else:
            st.sidebar.warning(f"Delete '{selected_project}'?")
            col1, col2 = st.sidebar.columns(2)
            if col1.button("✔️ Yes", type="primary", use_container_width=True):
                delete_project_file(selected_project)
                del st.session_state.projects[selected_project]
                st.session_state.current_project = None
                st.session_state.confirm_delete = False
                st.rerun()
            if col2.button("✖️ No", use_container_width=True):
                st.session_state.confirm_delete = False
                st.rerun()
    else:
        st.sidebar.info("No projects created yet. Create one above!")

    # --- Main Area: Active Project View ---
    if st.session_state.current_project:
        project_name = st.session_state.current_project
        project_data = st.session_state.projects[project_name]
        
        # Header with Title and Export Button
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col1:
            st.title(f"📁 Project: {project_name}")
        with header_col2:
            st.write("") # Padding
            if st.button("📄 Generate PDF Export", use_container_width=True):
                with st.spinner("Creating PDF..."):
                    pdf_bytes = export_to_pdf(project_name, project_data)
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"{project_name}_Quiz.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        # Add Video Section
        with st.expander("➕ Add YouTube Video to Project", expanded=False):
            youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
            if st.button("Fetch & Add Video"):
                if youtube_url:
                    video_id = extract_video_id(youtube_url)
                    if video_id:
                        with st.spinner("Fetching title and transcript..."):
                            title = fetch_video_title(video_id)
                            transcript = fetch_transcript(video_id)
                            
                            if "Could not retrieve a transcript" in transcript or "No transcript found" in transcript:
                                st.error("Error: Transcript not found or disabled for this video.")
                            elif "Video unavailable" in transcript:
                                st.error("Error: Video is unavailable.")
                            else:
                                # Add to project
                                project_data["videos"].append({
                                    "title": title,
                                    "url": youtube_url,
                                    "transcript": transcript,
                                    "id": video_id,
                                    "questions": []
                                })
                                save_project(project_name, project_data)
                                st.success(f"Added: {title}")
                                st.rerun()
                    else:
                        st.error("Invalid YouTube URL.")
                else:
                    st.warning("Please enter a URL.")

        st.divider()

        # Problem Sets (Videos)
        if project_data["videos"]:
            for idx, video in enumerate(project_data["videos"]):
                pset_num = idx + 1
                
                # Determine PSet Status for the Header
                has_questions = len(video.get("questions", [])) > 0
                warnings = [q for q in video.get("questions", []) if not q.get("verified")]
                
                if not has_questions:
                    header_icon = "📝"
                    header_text = f"Problem Set #{pset_num}: {video['title']} (Not Started)"
                elif warnings:
                    header_icon = "⚠️"
                    header_text = f"Problem Set #{pset_num}: {video['title']} (Action Required)"
                else:
                    header_icon = "✅"
                    header_text = f"Problem Set #{pset_num}: {video['title']} (Ready)"

                with st.expander(f"{header_icon} {header_text}"):
                    # Control Bar Alignment inside the expander
                    col_num, col_gen, col_fix, col_trans, col_del = st.columns([0.1, 0.25, 0.15, 0.25, 0.25])
                    
                    with col_num:
                        num_q = st.number_input(f"Questions", min_value=1, max_value=20, value=5, key=f"num_{idx}", label_visibility="collapsed")
                    
                    gen_label = "✨ Regenerate" if has_questions else "✨ Generate"
                    
                    with col_gen:
                        if st.button(gen_label, key=f"gen_{idx}", disabled=not st.session_state.llm_connected, use_container_width=True):
                            with st.spinner("Processing..."):
                                if has_questions:
                                    video['questions'] = fix_flagged_questions(video['transcript'], video)
                                else:
                                    video['questions'] = generate_questions(video['transcript'], num_q)
                                save_project(project_name, project_data)
                                st.rerun()
                    
                    with col_fix:
                        if warnings:
                            if st.button("🛠️ Fix", key=f"fix_{idx}", use_container_width=True):
                                with st.spinner("Fixing ambiguous questions..."):
                                    video['questions'] = fix_flagged_questions(video['transcript'], video)
                                    save_project(project_name, project_data)
                                    st.rerun()
                    
                    with col_trans:
                        st.download_button(
                            label="📄 Transcript",
                            data=video['transcript'],
                            file_name=f"{video['title']}_Transcript.txt",
                            mime="text/plain",
                            key=f"trans_dl_{idx}",
                            use_container_width=True
                        )
                    
                    with col_del:
                        confirm_key = f"confirm_del_vid_{idx}"
                        if confirm_key not in st.session_state:
                            st.session_state[confirm_key] = False
                            
                        if not st.session_state[confirm_key]:
                            if st.button("🗑️ Delete PSet", key=f"del_{idx}", use_container_width=True):
                                st.session_state[confirm_key] = True
                                st.rerun()
                        else:
                            st.error("Sure?")
                            c1, c2 = st.columns(2)
                            if c1.button("✔️", key=f"yes_{idx}", use_container_width=True):
                                project_data["videos"].pop(idx)
                                save_project(project_name, project_data)
                                del st.session_state[confirm_key]
                                st.rerun()
                            if c2.button("✖️", key=f"no_{idx}", use_container_width=True):
                                st.session_state[confirm_key] = False
                                st.rerun()

                    st.divider()

                    # Display Questions inside the expander
                    if has_questions:
                        for q_idx, q in enumerate(video["questions"]):
                            status_icon = "✅" if q.get("verified") else "⚠️"
                            st.write(f"**Q{q_idx+1}: {q['question']}** {status_icon}")
                            for i, choice in enumerate(q['choices']):
                                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;{chr(65+i)}) {choice}")
                            
                            if not q.get("verified"):
                                st.warning(f"AI suggested: **{q.get('ai_verification_mismatch', 'Unknown')}** instead of **{q['answer_letter']}**")
                        
                        st.divider()
                        ans_str = ", ".join([f"Q{i+1}: {q['answer_letter']}" for i, q in enumerate(video['questions'])])
                        st.info(f"Answer Key: {ans_str}")
                    else:
                        st.info("Click Generate to create questions for this Problem Set.")
        else:
            st.info("No videos added to this project yet.")
    else:
        st.title("📺 English Question Generator")
        st.write("Welcome! Create or select a project to start generating comprehension questions.")

if __name__ == "__main__":
    main()
