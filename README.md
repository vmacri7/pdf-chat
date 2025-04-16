# pdf-chat

this is a flask webapp that allows users to upload a pdf and chat with it using their voice. the app sends the pdf and audio to the gemini llm, receives a response, and uses google tts to speak the response aloud. the app is structured for deployment on google cloud run.

## features
- upload a pdf file
- record and upload audio to chat with your pdf
- gemini llm processes the pdf and audio
- google tts reads the response aloud

## running locally
1. install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. set up your google cloud credentials and api keys in a `.env` file.
3. run the app:
   ```
   python main.py
   ```

## deployment
- designed for deployment on google cloud run

## folders
- `uploads/pdfs/` for uploaded pdf files
- `uploads/audio/` for uploaded audio files
