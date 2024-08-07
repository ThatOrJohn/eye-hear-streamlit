# Eyehear 👁️👂

A Streamlit app using Google Gemini to transcribe doorbell camera video.  The uploaded video is transcribed, and this transcription is converted to audio which is automatically played.

This could be particularly handy for the blind (or anyone that doesn't feel like watching the video clip).


### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Place Gemini API key in `.streamlit/secrets.toml`

   ```
   GEMINI_API_KEY = "<your key here>"
   ```

3. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```
