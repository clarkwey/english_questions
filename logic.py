from youtube_transcript_api import YouTubeTranscriptApi
import re
import os
import json
import requests
from fpdf import FPDF

DATA_DIR = "data"
LLM_URL = "http://localhost:8080/v1/chat/completions"

def ensure_data_dir():
    """Ensures the data directory exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_project(project_name, project_data):
    """Saves a project to a JSON file."""
    ensure_data_dir()
    file_path = os.path.join(DATA_DIR, f"{project_name}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=4)

def load_all_projects():
    """Loads all projects from the data directory."""
    ensure_data_dir()
    projects = {}
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            project_name = filename[:-5]
            file_path = os.path.join(DATA_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    projects[project_name] = json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return projects

def delete_project_file(project_name):
    """Deletes the JSON file for a project."""
    file_path = os.path.join(DATA_DIR, f"{project_name}.json")
    if os.path.exists(file_path):
        os.remove(file_path)

def check_llm_status():
    """Checks if the local LLM server is running."""
    try:
        # Use a short timeout for the status check
        response = requests.get("http://localhost:8080/v1/models", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def generate_questions(transcript, count):
    """
    Generates and verifies multiple-choice questions using a two-pass system.
    Pass 1: Generate questions with SAT-style methodology focused on listening.
    Pass 2: Re-feed questions to verify the answers are clear and unambiguous.
    """
    # --- Pass 1: Advanced Generation ---
    generation_prompt = f"""
    You are an expert SAT English examiner. Based on the following transcript, generate {count} challenging multiple-choice questions for college-level students.
    
    METHODOLOGY:
    - Questions must target LISTENING COMPREHENSION specifically.
    - Focus on spoken nuances: emphasis, rhetorical transitions, implied meaning, and key arguments heard in the audio.
    - Focus on inference, tone, author's purpose, and evidence-based reasoning.
    - DO NOT ask low-level questions (e.g., "What is the main topic?", "What is the title?").
    - Distractors must be plausible but definitively incorrect.
    - Ensure correct answers are randomly distributed across positions A, B, C, and D.
    - Avoid references to "the text" or "the transcript"; use "the speaker" or "the video".
    
    OUTPUT FORMAT:
    - Output EXCLUSIVELY a JSON array.
    - DO NOT include prefixes like "A)", "B)", etc., in the "choices" strings. Just the choice text itself.
    
    JSON structure:
    [
      {{
        "question": "The question text",
        "choices": ["Option text 1", "Option text 2", "Option text 3", "Option text 4"],
        "answer_index": 0,
        "answer_letter": "A"
      }}
    ]
    
    Transcript:
    {transcript[:4000]}
    """
    
    try:
        # Pass 1: Get Questions
        payload = {
            "model": "local-model",
            "messages": [{"role": "user", "content": generation_prompt}],
            "temperature": 0.8
        }
        response = requests.post(LLM_URL, json=payload, timeout=120)
        if response.status_code != 200:
            return None
            
        content = response.json()['choices'][0]['message']['content']
        clean_content = re.sub(r'```json|```', '', content).strip()
        generated_questions = json.loads(clean_content)
        
        # --- Pass 2: Independent Verification ---
        verified_questions = []
        for q in generated_questions:
            verification_prompt = f"""
            Identify the correct answer for the following question based ONLY on the provided text.
            
            Text:
            {transcript[:4000]}
            
            Question: {q['question']}
            Choices:
            A) {q['choices'][0]}
            B) {q['choices'][1]}
            C) {q['choices'][2]}
            D) {q['choices'][3]}
            
            Return ONLY the letter of the correct answer (A, B, C, or D).
            """
            
            v_payload = {
                "model": "local-model",
                "messages": [{"role": "user", "content": verification_prompt}],
                "temperature": 0.1 # Low temperature for factual consistency
            }
            v_response = requests.post(LLM_URL, json=v_payload, timeout=30)
            
            if v_response.status_code == 200:
                ai_verification = v_response.json()['choices'][0]['message']['content'].strip().upper()
                if q['answer_letter'] in ai_verification:
                    q['verified'] = True
                else:
                    q['verified'] = False
                    q['ai_verification_mismatch'] = ai_verification
            else:
                q['verified'] = False
                q['ai_verification_mismatch'] = "Verification Failed"
            
            verified_questions.append(q)
            
        return verified_questions
        
    except Exception as e:
        print(f"Generation/Verification error: {e}")
        return None

def fix_flagged_questions(transcript, video_data):
    """
    Surgically fixes only the questions that failed verification.
    Ensures new questions are unrelated to existing ones and pass verification.
    """
    existing_questions = video_data.get("questions", [])
    # Track all question texts to prevent repeats
    all_question_texts = [q['question'] for q in existing_questions]
    
    flagged_indices = [i for i, q in enumerate(existing_questions) if not q.get("verified")]
    
    if not flagged_indices:
        return existing_questions

    for idx in flagged_indices:
        attempts = 0
        success = False
        
        while attempts < 3 and not success:
            attempts += 1
            
            # Prompt the AI to generate a BRAND NEW question, avoiding existing ones
            avoid_list = "\n".join([f"- {txt}" for txt in all_question_texts])
            fix_prompt = f"""
            You are an expert SAT English examiner. Generate a BRAND NEW, college-level listening comprehension question based on the transcript.
            
            TRANSCRIPT:
            {transcript[:4000]}
            
            DO NOT repeat or base the question on any of these existing questions:
            {avoid_list}
            
            METHODOLOGY:
            - Focus on high-level inference or spoken nuances.
            - Ensure the correct answer is definitive.
            - Output ONLY a JSON object for ONE question.
            
            JSON structure:
            {{
              "question": "The new question text",
              "choices": ["Option 1", "Option 2", "Option 3", "Option 4"],
              "answer_index": 0,
              "answer_letter": "A"
            }}
            """
            
            try:
                payload = {
                    "model": "local-model",
                    "messages": [{"role": "user", "content": fix_prompt}],
                    "temperature": 0.9 # Higher temperature for variety
                }
                response = requests.post(LLM_URL, json=payload, timeout=60)
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    clean_content = re.sub(r'```json|```', '', content).strip()
                    new_q = json.loads(clean_content)
                    
                    # --- Immediate Self-Verification ---
                    v_prompt = f"""
                    Identify the correct answer based on the text.
                    Text: {transcript[:4000]}
                    Question: {new_q['question']}
                    Choices: A) {new_q['choices'][0]} B) {new_q['choices'][1]} C) {new_q['choices'][2]} D) {new_q['choices'][3]}
                    Return ONLY the letter (A, B, C, or D).
                    """
                    v_res = requests.post(LLM_URL, json={"model": "local-model", "messages": [{"role": "user", "content": v_prompt}], "temperature": 0.1}, timeout=30)
                    
                    if v_res.status_code == 200:
                        v_ans = v_res.json()['choices'][0]['message']['content'].strip().upper()
                        if new_q['answer_letter'] in v_ans:
                            new_q['verified'] = True
                            success = True
                            # Update the set and the avoidance list
                            existing_questions[idx] = new_q
                            all_question_texts.append(new_q['question'])
                        else:
                            # If it fails, we loop and try again (up to 3 times)
                            new_q['verified'] = False
                            new_q['ai_verification_mismatch'] = v_ans
                            existing_questions[idx] = new_q
            except Exception as e:
                print(f"Surgical fix attempt {attempts} failed: {e}")
                
    return existing_questions

def export_to_pdf(project_name, project_data):
    """Exports the project to a PDF file with modern fpdf2 syntax and robust alignment."""
    pdf = FPDF(unit='mm', format='A4')
    pdf.set_margins(12, 12, 12) # Slightly larger margins for better readability
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    
    def safe_text(text):
        """Cleans text to avoid FPDF character encoding issues."""
        if not text: return ""
        replacements = {'\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...'}
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text.encode('latin-1', 'ignore').decode('latin-1')

    # Project Title
    pdf.set_font("helvetica", 'B', 14)
    pdf.cell(0, 10, text=safe_text(f"English Question Bank: {project_name}"), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    for idx, video in enumerate(project_data.get("videos", [])):
        pset_num = idx + 1
        
        # Check for space before adding a new PSet; if less than 30mm, new page
        if pdf.get_y() > 260:
            pdf.add_page()

        # PSet Header
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_fill_color(240, 240, 240)
        # Use multi_cell for header too in case title is very long
        pdf.multi_cell(0, 6, text=safe_text(f"PSet #{pset_num}: {video['title']}"), fill=True, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", 'I', 8)
        pdf.multi_cell(0, 4, text=safe_text(f"URL: {video['url']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
        if "questions" in video and video["questions"]:
            for q_idx, q in enumerate(video["questions"]):
                # Reset X to margin before each question
                pdf.set_x(12)
                
                # Question Text
                pdf.set_font("helvetica", 'B', 9)
                pdf.multi_cell(0, 5, text=safe_text(f"Q{q_idx+1}. {q['question']}"), new_x="LMARGIN", new_y="NEXT")
                
                # Choices - Using multi_cell for wrapping and explicit indents
                pdf.set_font("helvetica", '', 9)
                letters = ["A", "B", "C", "D"]
                for i, choice in enumerate(q['choices']):
                    pdf.set_x(18) # Indent choices by 6mm from question
                    pdf.multi_cell(0, 4, text=safe_text(f"{letters[i]}) {choice}"), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
            
            # Answer Key
            pdf.set_x(12)
            pdf.set_font("helvetica", 'I', 8)
            answers = [f"Q{i+1}: {q['answer_letter']}" for i, q in enumerate(video["questions"])]
            pdf.multi_cell(0, 4, text=safe_text("Answers: " + ", ".join(answers)), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
        else:
            pdf.set_x(12)
            pdf.set_font("helvetica", 'I', 9)
            pdf.multi_cell(0, 5, text="No questions generated.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            
    return bytes(pdf.output())

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
