import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client, Client
import tempfile
import json
from pathlib import Path
from PIL import Image

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'gif'}
CHUNK_DURATION = 15
FRAME_INTERVAL = 10

# Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Storage bucket
STORAGE_BUCKET = 'broll-videos'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return send_from_directory('.', 'index_semantic.html')

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """Get all videos with their visual analysis"""
    try:
        # Get videos from Supabase
        videos_response = supabase.table('videos').select('*').execute()
        videos = videos_response.data
        
        # Get visual frames for each video
        for video in videos:
            frames_response = supabase.table('visual_frames').select('*').eq('video_id', video['id']).execute()
            video['visual_frames'] = frames_response.data
            
            # Add Supabase Storage URL if not present
            if not video.get('supabase_video_url'):
                video['supabase_video_url'] = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/videos/{video['filename']}"
        
        return jsonify(videos)
    
    except Exception as e:
        print(f"Error getting videos: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    """Semantic search with multi-layer validation"""
    try:
        data = request.json
        query = data.get('query', '').strip().lower()
        
        if not query:
            return jsonify([])
        
        print(f"\n🔍 SEARCH QUERY: '{query}'")
        
        # Get all videos with visual frames
        videos_response = supabase.table('videos').select('*').execute()
        all_videos = videos_response.data
        
        results = []
        
        for video in all_videos:
            # Get visual frames for this video
            frames_response = supabase.table('visual_frames').select('*').eq('video_id', video['id']).execute()
            frames = frames_response.data
            
            for frame in frames:
                # Search in all tag fields
                searchable_text = f"{frame.get('visual_description', '')} {frame.get('emotion_tags', '')} {frame.get('laugh_tags', '')} {frame.get('contextual_tags', '')} {frame.get('character_tags', '')} {frame.get('semantic_tags', '')} {frame.get('series_movie', '')} {frame.get('actors', '')} {video.get('custom_tags', '')}".lower()
                
                if query in searchable_text:
                    # Add to results
                    result = {
                        'id': video['id'],
                        'filename': video['filename'],
                        'duration': video.get('duration'),
                        'thumbnail': video.get('thumbnail'),
                        'supabase_video_url': video.get('supabase_video_url') or f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/videos/{video['filename']}",
                        'custom_tags': video.get('custom_tags', ''),
                        'visual_frames': [frame]
                    }
                    results.append(result)
                    break  # Only add video once
        
        print(f"✅ Found {len(results)} results")
        return jsonify(results)
    
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_video():
    """Upload video to Supabase Storage"""
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file'}), 400
        
        file = request.files['video']
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Upload to Supabase Storage
            file_data = file.read()
            
            storage_path = f"videos/{filename}"
            supabase.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                file_data,
                file_options={"content-type": file.content_type, "upsert": "true"}
            )
            
            # Get public URL
            video_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"
            
            # Add to database
            video_data = {
                'filename': filename,
                'duration': 0,  # Will be updated later
                'status': 'pending',
                'supabase_video_url': video_url
            }
            
            result = supabase.table('videos').insert(video_data).execute()
            video_id = result.data[0]['id']
            
            return jsonify({
                'success': True,
                'video_id': video_id,
                'filename': filename,
                'url': video_url
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
    
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete video from database and storage"""
    try:
        # Get video info
        video_response = supabase.table('videos').select('filename').eq('id', video_id).execute()
        
        if not video_response.data:
            return jsonify({'error': 'Video not found'}), 404
        
        filename = video_response.data[0]['filename']
        
        # Delete from storage
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([f"videos/{filename}"])
        except:
            pass  # Continue even if file doesn't exist in storage
        
        # Delete from database (cascades to clips and visual_frames)
        supabase.table('videos').delete().eq('id', video_id).execute()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Delete error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/add_custom_tag', methods=['POST'])
def add_custom_tag():
    """Add custom tag to video"""
    try:
        data = request.json
        video_id = data.get('video_id')
        tag = data.get('tag', '').strip()
        
        if not video_id or not tag:
            return jsonify({'error': 'Missing video_id or tag'}), 400
        
        # Get current custom tags
        video_response = supabase.table('videos').select('custom_tags').eq('id', video_id).execute()
        
        if not video_response.data:
            return jsonify({'error': 'Video not found'}), 404
        
        current_tags = video_response.data[0].get('custom_tags', '')
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip()]
        
        if tag not in tags_list:
            tags_list.append(tag)
        
        new_tags = ', '.join(tags_list)
        
        # Update database
        supabase.table('videos').update({'custom_tags': new_tags}).eq('id', video_id).execute()
        
        return jsonify({'success': True, 'custom_tags': new_tags})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_custom_tag', methods=['POST'])
def delete_custom_tag():
    """Delete custom tag from video"""
    try:
        data = request.json
        video_id = data.get('video_id')
        tag = data.get('tag', '').strip()
        
        if not video_id or not tag:
            return jsonify({'error': 'Missing video_id or tag'}), 400
        
        # Get current custom tags
        video_response = supabase.table('videos').select('custom_tags').eq('id', video_id).execute()
        
        if not video_response.data:
            return jsonify({'error': 'Video not found'}), 404
        
        current_tags = video_response.data[0].get('custom_tags', '')
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip()]
        
        if tag in tags_list:
            tags_list.remove(tag)
        
        new_tags = ', '.join(tags_list)
        
        # Update database
        supabase.table('videos').update({'custom_tags': new_tags}).eq('id', video_id).execute()
        
        return jsonify({'success': True, 'custom_tags': new_tags})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'supabase_connected': SUPABASE_URL is not None,
        'openai_configured': os.getenv('OPENAI_API_KEY') is not None
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5002))
    print(f"🚀 Starting B-roll Mapper on port {port}")
    print(f"📊 Supabase URL: {SUPABASE_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
