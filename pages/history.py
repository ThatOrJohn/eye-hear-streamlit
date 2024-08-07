import json
import streamlit as st
import pandas as pd

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.oauth2 import service_account

GUEST_USER_ID = "f3d98f8c-cf8d-40a3-b5c3-5c7cd5e2b52a"

def get_user_id():
    return GUEST_USER_ID

st.title("EyeHear History")

key_dict = json.loads(st.secrets.FIREBASE_KEY)
credentials = service_account.Credentials.from_service_account_info(key_dict)
firestore_db = firestore.Client(credentials=credentials, project="eyehear-firebase")
collection = firestore_db.collection("videos")

query_last_20_videos = collection.where(filter=FieldFilter("user_id", "==", get_user_id())).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20)

results = query_last_20_videos.get()
video_list = []

for video in results:
    video_list.append(video.to_dict())

video_df = pd.DataFrame.from_dict(video_list, orient='columns')
video_df = video_df.drop(columns=['audio_location', 'user_id'])
cols = ['timestamp', 'description', 'humans_detected', 'animals_detected']
video_df = video_df[cols + [c for c in video_df.columns if c not in cols]]

st.write(video_df)
