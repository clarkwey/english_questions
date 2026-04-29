import streamlit as st
from logic import extract_video_id, fetch_transcript, fetch_video_title

def init_session_state():
    """Initializes the session state for projects if it doesn't exist."""
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    if 'current_project' not in st.session_state:
        st.session_state.current_project = None

def main():
    st.set_page_config(page_title="English Question Generator", page_icon="📺", layout="wide")
    init_session_state()

    # --- Sidebar: Project Management ---
    st.sidebar.title("📁 Projects")
    
    # Create new project
    new_project_name = st.sidebar.text_input("Create New Project", placeholder="e.g., IELTS Grammar")
    if st.sidebar.button("Add Project"):
        if new_project_name and new_project_name not in st.session_state.projects:
            st.session_state.projects[new_project_name] = {"videos": []}
            st.session_state.current_project = new_project_name
            st.sidebar.success(f"Project '{new_project_name}' created!")
        elif new_project_name in st.session_state.projects:
            st.sidebar.warning("Project already exists.")
        else:
            st.sidebar.error("Please enter a project name.")

    st.sidebar.divider()

    # Project Selector
    project_list = list(st.session_state.projects.keys())
    if project_list:
        selected_project = st.sidebar.radio(
            "Select a Project", 
            project_list, 
            index=project_list.index(st.session_state.current_project) if st.session_state.current_project in project_list else 0
        )
        st.session_state.current_project = selected_project
        
        if st.sidebar.button("Delete Project", type="secondary"):
            del st.session_state.projects[selected_project]
            st.session_state.current_project = None
            st.rerun()
    else:
        st.sidebar.info("No projects created yet. Create one above!")

    # --- Main Area: Active Project View ---
    if st.session_state.current_project:
        project_name = st.session_state.current_project
        project_data = st.session_state.projects[project_name]
        
        st.title(f"📁 Project: {project_name}")
        
        # Add Video Section
        with st.expander("➕ Add YouTube Video to Project", expanded=True):
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
                                    "id": video_id
                                })
                                st.success(f"Added: {title}")
                    else:
                        st.error("Invalid YouTube URL.")
                else:
                    st.warning("Please enter a URL.")

        st.divider()

        # Video Gallery
        if project_data["videos"]:
            st.subheader("📺 Videos in this Project")
            for idx, video in enumerate(project_data["videos"]):
                with st.container():
                    col1, col2 = st.columns([0.8, 0.2])
                    with col1:
                        with st.expander(f"🎬 {video['title']}"):
                            st.write(f"**URL:** {video['url']}")
                            st.text_area("Transcript", video['transcript'], height=200, key=f"trans_{idx}")
                            
                            st.download_button(
                                label="Download (.txt)",
                                data=video['transcript'],
                                file_name=f"{video['title']}.txt",
                                mime="text/plain",
                                key=f"dl_{idx}"
                            )
                    with col2:
                        if st.button("🗑️ Remove", key=f"del_{idx}"):
                            project_data["videos"].pop(idx)
                            st.rerun()
        else:
            st.info("No videos added to this project yet.")
    else:
        st.title("📺 YouTube Transcript Manager")
        st.write("Welcome! Please create or select a project from the sidebar to get started.")

if __name__ == "__main__":
    main()
