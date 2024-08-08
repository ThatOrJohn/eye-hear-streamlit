import datetime
import json
import os
import streamlit as st
import time
import google.generativeai as genai

from google.cloud import firestore
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.oauth2 import service_account
from gtts import gTTS
from io import BytesIO
from st_files_connection import FilesConnection

MODEL_TO_USE = "flash-1.5"
GEMINI_MODELS = {
    "flash-1.5": "gemini-1.5-flash",
    "pro-1.5": "gemini-1.5-pro"
}

st.title("EyeHear 👁️👂")

CLOUD_STORAGE_BUCKET = "eyehear-firebase.appspot.com"
GUEST_USER_ID = "f3d98f8c-cf8d-40a3-b5c3-5c7cd5e2b52a"

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

def update_key():
    st.session_state.uploader_key += 1

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
and actions that exist in the video.  Transcribe any detectable audio.  
Keep your descriptions under 1000 words per video.  Do not state the video is
a recording from a doorbell camera, or that it is from a Ring doorbell,
or anything regarding the positioning of the camera.
"""

def get_gemini_model():
    return GEMINI_MODELS[MODEL_TO_USE]


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

    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH
    }

    return genai.GenerativeModel(
    model_name=get_gemini_model(),
    generation_config=generation_config,
    system_instruction=prompt_json)

def generate_audio(video_description):
    mp3_fp = BytesIO()
    tts = gTTS(video_description, lang='en', timeout=120)
    tts.write_to_fp(mp3_fp)
    return mp3_fp


def store_audio_file(mp3_bytes_io, video_file_name):
    try:
        user_id = get_user_id()
        print(f"store_audio_file() for user_id: {user_id}, video: {video_file_name}")
        mp3_file_name = os.path.splitext(video_file_name)[0]+'.mp3'
        tmp_mp3_file = f"/tmp/{mp3_file_name}"

        cloud_mp3_file = f"{CLOUD_STORAGE_BUCKET}/audio/{user_id}/{mp3_file_name}"
        print(f"Writing {cloud_mp3_file} to cloud storage")

        with open(tmp_mp3_file, "wb") as tmp_file:
            tmp_file.write(mp3_bytes_io.getbuffer())

        file_storage_conn = st.connection('gcs', type=FilesConnection)
        with file_storage_conn.open(cloud_mp3_file, "wb") as gcs_file:
            gcs_file.write(mp3_bytes_io.getbuffer())
    except Exception as e:
        print(f"Exception: {e}")
        st.error("Error storing audio file", icon="🚨")
    finally:
        if os.path.exists(tmp_mp3_file):
            os.remove(tmp_mp3_file)
    return cloud_mp3_file


def store_video_details(video_details):
    try:
        print("begin store_video_details")
        key_dict = json.loads(st.secrets.FIREBASE_KEY)

        credentials = service_account.Credentials.from_service_account_info(key_dict)
        firestore_db = firestore.Client(credentials=credentials, project="eyehear-firebase")
        collection = firestore_db.collection("videos")
        video_document = collection.add(document_data=video_details)
    except Exception as e:
        print(f"Exception: {e}")
        st.error("Error storing video description", icon="🚨")
    print("completed store_video_details")

model = create_gemini_model()

st.write(
    "Proof of concept"
)
st.write(
    """For now we'll manually upload an mp4 doorbell video.  Ultimately, this would 
    listen for incoming doorbell events, and automatically read transcriptions aloud."""
)

uploaded_file = st.file_uploader("Upload doorbell video", type=['mp4'], key=f"uploader_{st.session_state.uploader_key}")
container = st.container(border=True)

if uploaded_file is not None:
    time_received = datetime.datetime.now().replace(microsecond=0).isoformat()
    file_name = uploaded_file.name
    tmp_file = f"/tmp/{file_name}"
    
    with open(tmp_file, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.toast("Processing new video")
    response = model.generate_content(tmp_file)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    os.remove(tmp_file)
    container.header(f"Video Received at {time_received}")
    st.video(uploaded_file)
    container.header("Video Transcription")
    container.subheader("Audio")
    container.audio(mp3_stream, autoplay=True)
    container.subheader("Text")
    container.write(video_description)
    cloud_mp3_file = store_audio_file(mp3_stream, file_name)

    response_data['user_id'] = get_user_id()
    response_data['timestamp'] = time_received
    response_data['audio_location'] = cloud_mp3_file
    store_video_details(response_data)

if st.button("Example video", type="primary", on_click=update_key):
    # just send the video to Gemini and generate audio
    example_url = "https://github.com/ThatOrJohn/eye-hear-streamlit/raw/main/examples/Ring_FrontDoor_202408081615.mp4"
    st.toast("Processing example video")
    response = model.generate_content(example_url)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    container.header("Video received (example)")
    st.video(example_url)
    container.header("Video Transcription")
    container.subheader("Audio")
    container.audio(mp3_stream, autoplay=True)
    container.subheader("Text")
    container.write(video_description)
