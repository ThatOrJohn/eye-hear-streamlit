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

prompt_json = """Describe the video with details that would be 
included in a police report.   The description should include: 
1. If any humans are detected
 a. provide a total headcount 
 b. describe each human's appearance and gestures 
2. If any animals are detected 
 a. provide a count of each type 
3. Describe any vehicles present 
4. Do not read watermarks, but do read text on clothing and vehicles. 
5. Do not opine on whether the video depicts a real situation or not
6. Do not mention what recorded the video

The response should use this JSON schema:

{'description': str,\n'humans_detected': bool,\n'animals_detected': bool}

A good description might look like this:

There are 2 people present.  One is dressed as a creepy clown, and 
the other is wearing a brown shirt that says UPS.  The person in 
the clown is holding a knife.  There is 1 orange cat behind them."""

prompt_json2 = """
Accurately, and succinctly describe the contents of the attached video 
using this JSON schema:

{'description': str,
'humans_detected': bool,
'animals_detected': bool}

Description should contain information that would be useful for 
documenting in a police report.  Pay particular attention to people,
gestures, animals, and vehicles.  You are only to discuss the contents 
and actions that exist in the video.  Transcribe any detectable audio.  
Keep your descriptions under 700 words per video.  Do not state the video is
a recording from a doorbell camera, or that it is from a Ring doorbell,
or anything regarding the positioning of the camera.
"""

def get_gemini_model():
    return GEMINI_MODELS[MODEL_TO_USE]


def create_gemini_model():
    # store api key in .streamlit/secrets.toml
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    generation_config = {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json", 
    }

    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH
    }

    return genai.GenerativeModel(
    model_name=get_gemini_model(),
    generation_config=generation_config,
    system_instruction=prompt_json,
    safety_settings=safety_settings)

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

# Begin Gemini file upload
def upload_to_gemini(path, mime_type=None):
  """Uploads the given file to Gemini.

  See https://ai.google.dev/gemini-api/docs/prompting_with_media
  """
  file = genai.upload_file(path, mime_type=mime_type)
  print(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file

def wait_for_file_active(file):
    print("Waiting for file processing...")
    name = file.name
    gemini_file = genai.get_file(name)
    print(f"state {gemini_file.state.name}")
    while gemini_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        gemini_file = genai.get_file(name)
    if gemini_file.state.name != "ACTIVE":
        raise Exception(f"File {gemini_file.name} failed to process")
    print("...file ready")


# End Gemini file upload

model = create_gemini_model()

st.write(
    "Proof of Concept:  Audibly describe videos received by doorbell camera"
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
    
    gemini_file = upload_to_gemini(tmp_file, mime_type="video/mp4")
    wait_for_file_active(gemini_file)

    st.toast("Processing new video")
    #response = model.generate_content(tmp_file)
    response = model.generate_content(gemini_file)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    os.remove(tmp_file)
    container.header(f"Video Received at {time_received}")
    st.video(uploaded_file)
    container.header("Transcription")
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
    print(f"model config: {model._generation_config}")
    print(f"prompt: {model._system_instruction}")
    response = model.generate_content(example_url)
    response_data = json.loads(response.text)
    video_description = response_data.get('description')
    mp3_stream = generate_audio(video_description)
    container.header("Video received (example)")
    st.video(example_url)
    container.header("Transcription")
    container.subheader("Audio")
    container.audio(mp3_stream, autoplay=True)
    container.subheader("Text")
    container.write(video_description)
