import os
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from google.cloud import storage
from datetime import datetime
import google.generativeai as genai
from google.cloud import texttospeech

# initialize flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PDF_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs')
app.config['AUDIO_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')

# create upload directories if they don't exist
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# gcloud bucket name from env or default
BUCKET_NAME = "pdf-chat-bucket-convai"

# initialize gcloud storage client
storage_client = storage.Client()

# configure gemini api
GEMINI_API_KEY = os.environ.get('GEMINI_API')
genai.configure(api_key=GEMINI_API_KEY)

def upload_pdf_to_cloud(local_path, bucket_name=BUCKET_NAME):
    # upload the pdf to the gcloud bucket
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(os.path.basename(local_path))
    blob.content_type = 'application/pdf'
    blob.upload_from_filename(local_path)
    return blob.name

# allowed extensions
def allowed_pdf(filename):
    # only allow pdf files
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def allowed_audio(filename):
    # only allow wav files for now
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'wav'

# upload pdf endpoint
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'no pdf file part'}), 400
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'error': 'no selected file'}), 400
    if file and allowed_pdf(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['PDF_FOLDER'], filename)
        file.save(file_path)
        # upload to gcloud bucket
        cloud_filename = upload_pdf_to_cloud(file_path)
        return jsonify({'message': 'pdf uploaded successfully', 'filename': filename, 'cloud_filename': cloud_filename}), 200
    return jsonify({'error': 'invalid file type'}), 400

# upload audio endpoint
@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio_file' not in request.files:
        return jsonify({'error': 'no audio file part'}), 400
    file = request.files['audio_file']
    if file.filename == '':
        return jsonify({'error': 'no selected file'}), 400
    if file and allowed_audio(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['AUDIO_FOLDER'], filename)
        file.save(file_path)
        return jsonify({'message': 'audio uploaded successfully', 'filename': filename}), 200
    return jsonify({'error': 'invalid file type'}), 400

def ensure_pdf_local(pdf_filename):
    # ensure the pdf is available locally; download from gcs if not
    local_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)
    if not os.path.exists(local_path):
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(pdf_filename)
        if not blob.exists():
            return None
        # download the blob to the local path
        blob.download_to_filename(local_path)
    return local_path

# chat endpoint (pdf + audio to gemini, tts response)
@app.route('/chat', methods=['POST'])
def chat():
    pdf_filename = request.form.get('pdf_filename')
    if not pdf_filename:
        return jsonify({'error': 'missing pdf filename'}), 400
    # use helper to ensure local copy
    pdf_path = ensure_pdf_local(pdf_filename)
    if not pdf_path:
        return jsonify({'error': 'pdf file not found'}), 404
    # check for audio file in request
    if 'audio_file' not in request.files:
        return jsonify({'error': 'no audio file part'}), 400
    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({'error': 'no audio file selected'}), 400
    # save audio as user_[timestamp].wav
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    audio_filename = f'user_{timestamp}.wav'
    audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
    audio_file.save(audio_path)
    # call gemini with pdf and audio, print response
    response_text = call_gemini_with_pdf_and_audio(pdf_path, audio_path)
    print('gemini response:', response_text)
    # synthesize tts and save as ai_[timestamp].wav
    ai_audio_filename = call_tts(response_text, timestamp)
    ai_audio_url = url_for('get_audio', filename=ai_audio_filename)
    return jsonify({'response_text': response_text, 'tts_audio_url': ai_audio_url}), 200

# placeholder for gemini integration
def call_gemini_with_pdf_and_audio(pdf_path, audio_path):
    # upload pdf and audio to gemini
    pdf_file = genai.upload_file(pdf_path, mime_type='application/pdf')
    audio_file = genai.upload_file(audio_path, mime_type='audio/wav')
    # initialize gemini model
    model = genai.GenerativeModel(model_name='gemini-1.5-flash')
    # prompt for multimodal input
    prompt = "you are a helpful assistant. answer the user's question about the pdf based on the audio input."
    # send to gemini
    response = model.generate_content([pdf_file, audio_file, prompt])
    return response.text.strip() if hasattr(response, 'text') else str(response)

# placeholder for tts integration
def call_tts(text, timestamp):
    # synthesize speech using google tts
    tts_client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    # save audio as ai_[timestamp].wav
    ai_audio_filename = f'ai_{timestamp}.wav'
    ai_audio_path = os.path.join(app.config['AUDIO_FOLDER'], ai_audio_filename)
    with open(ai_audio_path, 'wb') as out:
        out.write(response.audio_content)
    return ai_audio_filename

# serve uploaded files
def serve_uploaded_file(folder, filename):
    return send_from_directory(folder, filename)

@app.route('/pdfs/<filename>')
def get_pdf(filename):
    return serve_uploaded_file(app.config['PDF_FOLDER'], filename)

@app.route('/audio/<filename>')
def get_audio(filename):
    return serve_uploaded_file(app.config['AUDIO_FOLDER'], filename)

# home page
@app.route('/')
def index():
    return render_template('index.html')

# list all pdf files in the gcloud bucket
@app.route('/list_pdfs', methods=['GET'])
def list_pdfs():
    pdfs = get_all_pdfs_from_bucket()
    return jsonify({'pdfs': pdfs})

def get_all_pdfs_from_bucket():
    # list all pdf files in the bucket
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs()
    pdfs = [blob.name for blob in blobs if blob.name.lower().endswith('.pdf')]
    return pdfs

if __name__ == '__main__':
    app.run(debug=True) 