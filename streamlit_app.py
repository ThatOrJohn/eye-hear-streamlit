import datetime
import json
import os
import streamlit as st
import time
import google.generativeai as genai

from gtts import gTTS
from io import BytesIO
from st_files_connection import FilesConnection

st.title("EyeHear 👁️👂")

CLOUD_STORAGE_BUCKET = "eyehear-firebase.appspot.com"
GUEST_USER_ID = "f3d98f8c-cf8d-40a3-b5c3-5c7cd5e2b52a"

def get_user_id():
    return GUEST_USER_ID

prompt_json = """
Describe the contents of the attached video using this JSON schema:

{'description': str,
'humans_detected': bool,
'animals_detected': bool}

Your description should contain information that would be useful for 
documenting in a police report.  Pay particular attention to people,
gestures, animals, and vehicles.  You are only to discuss the contents 
of provided videos.  Transcribe any detectable audio.  Keep your 
descriptions under 1500 words per video.  Do not state the video is
a recording from a doorbell camera, or that it is from a Ring doorbell,
or anything regarding the positioning of the camera.
"""

@st.cache_data
def create_gemini_model():
    # store api key in .streamlit/secrets.toml
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",  # "text/plain",
    }
    return genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=prompt_json)

def generate_audio(video_description):
    mp3_fp = BytesIO()
    tts = gTTS(video_description, lang='en', timeout=120)
    tts.write_to_fp(mp3_fp)
    return mp3_fp

@st.cache_data
def get_cloud_storage_connection():
    conn = st.connection('gcs', type=FilesConnection)
    return conn

def store_audio_file(mp3_bytes_io, video_file_name):
    user_id = get_user_id()
    print(f"store_audio_file() for user_id: {user_id}, video: {video_file_name}")
    mp3_file_name = os.path.splitext(video_file_name)[0]+'.mp3'
    tmp_mp3_file = f"/tmp/{mp3_file_name}"

    cloud_mp3_file = f"{CLOUD_STORAGE_BUCKET}/audio/{user_id}/{mp3_file_name}"
    print(f"Writing {cloud_mp3_file} to cloud storage")

    with open(tmp_mp3_file, "wb") as f:
        f.write(mp3_bytes_io.getbuffer())

    # conn = get_cloud_storage_connection()

    # with open(tmp_mp3_file, "rb") as local_file:
    conn = st.connection('gcs', type=FilesConnection)
    with conn.open(cloud_mp3_file, "wb") as gcs_file:
        gcs_file.write(mp3_bytes_io.getbuffer())

    os.remove(tmp_mp3_file)
    return cloud_mp3_file


model = create_gemini_model()

st.write(
    "Proof of concept"
)
st.write(
    "For now we'll manually upload an mp4 doorbell video.  Ultimately, this would listen for incoming doorbell events."
)

uploaded_file = st.file_uploader("Upload doorbell video", type=['mp4'])

if uploaded_file is not None:
    time_received = datetime.datetime.now().replace(microsecond=0).isoformat()
    file_name = uploaded_file.name
    tmp_file = f"/tmp/{file_name}"
    
    with open(tmp_file, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    response = model.generate_content(tmp_file)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    os.remove(tmp_file)
    st.video(uploaded_file)
    st.audio(mp3_stream, autoplay=True)
    cloud_mp3_file = store_audio_file(mp3_stream, file_name)

if st.button("Example video", type="primary"):
    example_url = "https://github.com/ThatOrJohn/eye-hear-streamlit/raw/main/examples/Ring_FrontDoor_202408061842.mp4"
    response = model.generate_content(example_url)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    st.video(example_url)
    st.audio(mp3_stream, autoplay=True)
