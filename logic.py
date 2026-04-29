from youtube_transcript_api import YouTubeTranscriptApi
import re

import requests

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

def fetch_video_title(video_id):
    """
    Fetches the title of a YouTube video using the oEmbed API.
    """
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("title", f"Video {video_id}")
        return f"Video {video_id}"
    except Exception:
        return f"Video {video_id}"

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
