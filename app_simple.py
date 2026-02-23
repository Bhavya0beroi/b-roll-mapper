import os
import sqlite3
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
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
            embedding TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_duration(video_path):
    """Get video duration using ffprobe."""
    try:
        cmd = [
            '/opt/homebrew/bin/ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return 0

def extract_audio(video_path):
    """Extract audio from video using ffmpeg."""
    try:
        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        cmd = [
            '/opt/homebrew/bin/ffmpeg',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'libmp3lame',
            '-q:a', '2',  # Quality
            '-y',  # Overwrite
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg stderr: {result.stderr}")
            raise Exception(f"FFmpeg failed with code {result.returncode}. Video might have no audio track or be corrupted.")
        
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
                response_format="verbose_json"
            )
        return transcript
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        raise

def create_embeddings(text):
    """Create embeddings using OpenAI API."""
    try:
        # Clean the text
        text = text.strip().replace('\n', ' ')[:8000]  # Limit to 8K chars
        
        print(f"    Calling OpenAI embeddings API...")
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        print(f"    Embedding received, converting to string...")
        
        # Store as comma-separated string
        embedding = ','.join(str(x) for x in response.data[0].embedding)
        print(f"    Embedding ready (length: {len(embedding)} chars)")
        return embedding
    except Exception as e:
        import traceback
        print(f"Error creating embedding: {e}")
        print(f"Full traceback:\n{traceback.format_exc()}")
        raise

def cosine_similarity(vec1_str, vec2_str):
    """Calculate cosine similarity between two vectors stored as strings."""
    vec1 = [float(x) for x in vec1_str.split(',')]
    vec2 = [float(x) for x in vec2_str.split(',')]
    
    # Dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    
    # Magnitudes
    mag1 = sum(a * a for a in vec1) ** 0.5
    mag2 = sum(b * b for b in vec2) ** 0.5
    
    # Cosine similarity
    return dot_product / (mag1 * mag2)

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
        video_duration = get_video_duration(video_path)
        
        # Process segments and create 15-second chunks
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        print("Creating semantic chunks...")
        segment_count = 0
        for segment in transcript.segments:
            start_time = segment.start
            end_time = segment.end
            text = segment.text.strip()
            
            if not text:
                continue
            
            # Create embedding using OpenAI
            segment_count += 1
            print(f"  Processing segment {segment_count}: {text[:50]}...")
            
            try:
                embedding = create_embeddings(text)
            except Exception as e:
                print(f"  Warning: Failed to create embedding for segment {segment_count}: {e}")
                continue
            
            # Store in database
            try:
                cursor.execute('''
                    INSERT INTO clips (filename, timestamp, duration, text, embedding)
                    VALUES (?, ?, ?, ?, ?)
                ''', (filename, start_time, min(CHUNK_DURATION, end_time - start_time), text, embedding))
            except Exception as e:
                print(f"  Warning: Failed to store segment {segment_count}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"Successfully processed {filename}")
        
    finally:
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("\n=== UPLOAD REQUEST RECEIVED ===")
    
    if 'file' not in request.files:
        print("ERROR: No file in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    print(f"File received: {file.filename}")
    
    if file.filename == '':
        print("ERROR: Empty filename")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        print(f"Saving to: {filepath}")
        
        # Save file
        file.save(filepath)
        print(f"File saved successfully")
        
        try:
            # Process video
            print(f"Starting video processing...")
            process_video(filepath, filename)
            print(f"Processing complete!")
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ERROR during processing:\n{error_detail}")
            return jsonify({'error': str(e), 'detail': error_detail}), 500
    
    print(f"ERROR: Invalid file type for {file.filename}")
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'results': []})
    
    # Create embedding for query using OpenAI
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = ','.join(str(x) for x in response.data[0].embedding)
    except Exception as e:
        return jsonify({'error': f'Failed to create query embedding: {str(e)}'}), 500
    
    # Search database
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, timestamp, duration, text, embedding FROM clips')
    
    results = []
    for row in cursor.fetchall():
        clip_id, filename, timestamp, duration, text, clip_embedding = row
        
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
    print("\n" + "="*60)
    print("🎥 B-ROLL MAPPER - READY TO USE!")
    print("="*60)
    print("✅ Using OpenAI API (no local ML dependencies)")
    print("✅ Fast and reliable")
    print("✅ Server running at: http://localhost:5001")
    print("="*60)
    print("\n⚠️  NOTE: FFmpeg is required for video processing")
    print("   Install with: brew install ffmpeg")
    print("="*60 + "\n")
    app.run(debug=True, port=5001)
