import streamlit as st
from logic import extract_video_id, fetch_transcript

def main():
    st.set_page_config(page_title="YouTube Transcript Fetcher", page_icon="📺")
    
    st.title("📺 YouTube Transcript Fetcher")
    st.write("Enter a YouTube URL below to extract its transcript.")

    youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("Fetch Transcript"):
        if youtube_url:
            video_id = extract_video_id(youtube_url)
            
            if video_id:
                with st.spinner(f"Fetching transcript for video ID: {video_id}..."):
                    transcript = fetch_transcript(video_id)
                    
                    if "Could not retrieve a transcript" in transcript or "No transcript found" in transcript:
                        st.error("Error: Transcript not found or disabled for this video.")
                    elif "Video unavailable" in transcript:
                        st.error("Error: Video is unavailable.")
                    else:
                        st.success("Transcript fetched successfully!")
                        st.text_area("Transcript Output", transcript, height=300)
                        
                        st.download_button(
                            label="Download Transcript (.txt)",
                            data=transcript,
                            file_name=f"transcript_{video_id}.txt",
                            mime="text/plain"
                        )
            else:
                st.error("Invalid YouTube URL. Please check the link and try again.")
        else:
            st.warning("Please enter a YouTube URL first.")

if __name__ == "__main__":
    main()
