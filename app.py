import os
import sqlite3
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import numpy as np
from dotenv import load_dotenv
import tempfile

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
DATABASE = 'broll.db'
CHUNK_DURATION = 15  # 15-second chunks

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize sentence transformer model
print("Loading embedding model...")
embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Embedding model loaded!")

# Database initialization
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            timestamp REAL NOT NULL,
            duration REAL NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_audio(video_path):
    """Extract audio from video and save as temporary file."""
    try:
        video = VideoFileClip(video_path)
        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        video.audio.write_audiofile(audio_path, verbose=False, logger=None)
        video.close()
        return audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        raise

def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper API."""
    try:
        with open(audio_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularity=["segment"]
            )
        return transcript
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        raise

def create_embeddings(text):
    """Create embeddings using sentence-transformers."""
    embedding = embedding_model.encode(text)
    return embedding.astype(np.float32).tobytes()

def process_video(video_path, filename):
    """Process video: extract audio, transcribe, create chunks, and store."""
    print(f"Processing video: {filename}")
    
    # Extract audio
    print("Extracting audio...")
    audio_path = extract_audio(video_path)
    
    try:
        # Transcribe
        print("Transcribing...")
        transcript = transcribe_audio(audio_path)
        
        # Get video duration
        video = VideoFileClip(video_path)
        video_duration = video.duration
        video.close()
        
        # Process segments and create 15-second chunks
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        print("Creating semantic chunks...")
        for segment in transcript.segments:
            start_time = segment['start']
            end_time = segment['end']
            text = segment['text'].strip()
            
            if not text:
                continue
            
            # Create embedding
            embedding = create_embeddings(text)
            
            # Store in database
            cursor.execute('''
                INSERT INTO clips (filename, timestamp, duration, text, embedding)
                VALUES (?, ?, ?, ?, ?)
            ''', (filename, start_time, min(CHUNK_DURATION, end_time - start_time), text, embedding))
        
        conn.commit()
        conn.close()
        
        print(f"Successfully processed {filename}")
        
    finally:
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file
        file.save(filepath)
        
        try:
            # Process video
            process_video(filepath, filename)
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'results': []})
    
    # Create embedding for query
    query_embedding = embedding_model.encode(query).astype(np.float32)
    
    # Search database
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, timestamp, duration, text, embedding FROM clips')
    
    results = []
    for row in cursor.fetchall():
        clip_id, filename, timestamp, duration, text, embedding_blob = row
        clip_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        
        # Calculate similarity
        similarity = cosine_similarity(query_embedding, clip_embedding)
        
        results.append({
            'id': clip_id,
            'filename': filename,
            'timestamp': timestamp,
            'duration': duration,
            'text': text,
            'similarity': float(similarity)
        })
    
    conn.close()
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top 20 results
    return jsonify({'results': results[:20]})

@app.route('/uploads/<path:filename>')
def serve_video(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/videos', methods=['GET'])
def list_videos():
    """List all uploaded videos."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT filename FROM clips')
    videos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify({'videos': videos})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
