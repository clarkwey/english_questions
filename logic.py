from youtube_transcript_api import YouTubeTranscriptApi
import re

def extract_video_id(url):
    """
    Extracts the video ID from a YouTube URL.
    Supports standard, shortened, and embed links.
    """
    regex = r"(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})"
    match = re.search(regex, url)
    if match:
        return match.group(1)
    return None

def fetch_transcript(video_id):
    """
    Fetches the transcript for a given video ID.
    Returns the transcript as a single string.
    """
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id).to_raw_data()
        # Combine the text from each segment
        transcript = " ".join([segment['text'] for segment in transcript_list])
        return transcript
    except Exception as e:
        return str(e)
