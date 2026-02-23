"""
B-Roll Mapper - Supabase PostgreSQL Version
Converted from SQLite to use Supabase for database and storage.

Environment variables required:
- SUPABASE_URL
- SUPABASE_SERVICE_KEY
- OPENAI_API_KEY

Schema note: Clips and visual_frames need embedding columns for semantic search.
Run the schema extension in supabase_schema_extended.sql if not present.
"""

import os
import subprocess
import math
import base64
import tempfile
import json
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Supabase config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BUCKET_NAME = 'broll-videos'

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
THUMBNAILS_FOLDER = 'thumbnails'
FRAMES_FOLDER = 'frames'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'gif'}
CHUNK_DURATION = 15
FRAME_INTERVAL = 10

os.makedirs(THUMBNAILS_FOLDER, exist_ok=True)
os.makedirs(FRAMES_FOLDER, exist_ok=True)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_video_duration(video_path):
    """Get video duration using ffprobe."""
    try:
        # Check multiple possible ffprobe locations
        ffprobe_paths = ['/opt/homebrew/bin/ffprobe', '/usr/bin/ffprobe', 'ffprobe']
        ffprobe = None
        for path in ffprobe_paths:
            if os.path.exists(path):
                ffprobe = path
                break
        if not ffprobe:
            ffprobe = 'ffprobe'  # Hope it's in PATH
        
        cmd = [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"❌ Error getting video duration: {e}")
        return 0


def generate_thumbnail(video_path, thumbnail_path, timestamp=1.0):
    """Generate video thumbnail using ffmpeg."""
    try:
        # Check multiple possible ffmpeg locations
        ffmpeg_paths = ['/opt/homebrew/bin/ffmpeg', '/usr/bin/ffmpeg', 'ffmpeg']
        ffmpeg = None
        for path in ffmpeg_paths:
            if os.path.exists(path):
                ffmpeg = path
                break
        if not ffmpeg:
            ffmpeg = 'ffmpeg'  # Hope it's in PATH
        
        cmd = [ffmpeg, '-i', video_path, '-ss', str(timestamp), '-vframes', '1', '-q:v', '2', '-y', thumbnail_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Thumbnail generation failed")
        return thumbnail_path
    except Exception as e:
        print(f"❌ Error generating thumbnail: {e}")
        return None


def extract_frames_for_analysis(video_path, video_duration, filename):
    """Extract frames at regular intervals for visual analysis."""
    try:
        frames = []
        video_base = os.path.splitext(filename)[0]
        
        # Check multiple possible ffmpeg locations
        ffmpeg_paths = ['/opt/homebrew/bin/ffmpeg', '/usr/bin/ffmpeg', 'ffmpeg']
        ffmpeg = None
        for path in ffmpeg_paths:
            if os.path.exists(path) or path == 'ffmpeg':
                ffmpeg = path
                break

        if video_duration <= 20:
            timestamps = [video_duration / 2]
        elif video_duration <= 60:
            timestamps = [video_duration / 3, video_duration * 2 / 3]
        else:
            timestamps = [video_duration * 0.25, video_duration * 0.5, video_duration * 0.75]

        for timestamp in timestamps:
            if timestamp >= video_duration:
                break
            frame_filename = f"{video_base}_frame_{int(timestamp)}s.jpg"
            frame_path = os.path.join(FRAMES_FOLDER, frame_filename)
            cmd = [ffmpeg, '-ss', str(timestamp), '-i', video_path, '-vframes', '1', '-q:v', '2', '-y', frame_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                frames.append({'timestamp': timestamp, 'path': frame_path, 'filename': frame_filename})
        return frames
    except Exception as e:
        print(f"❌ Error extracting frames: {e}")
        return []


def intelligently_generate_categorized_tags(analysis):
    """Generate comprehensive categorized tags from Vision API analysis."""
    description = str(analysis.get('description', ''))
    emotion = str(analysis.get('emotion', ''))
    deep_emotions = analysis.get('deep_emotions', '')
    scene_context = str(analysis.get('scene_context', ''))
    environment = str(analysis.get('environment', ''))
    people_description = str(analysis.get('people_description', ''))
    actors = analysis.get('actors', '')
    series_movie = str(analysis.get('series_movie', ''))
    media_type = str(analysis.get('media_type', 'Unknown'))
    tags = str(analysis.get('tags', ''))

    all_tags_list = []
    if tags:
        all_tags_list = tags.split(',') if isinstance(tags, str) else tags
        if not isinstance(all_tags_list, list):
            all_tags_list = [tags]
        all_tags_list = [t.strip() for t in all_tags_list if t and t.strip()]

    emotion_list = []
    laugh_list = []
    contextual_list = []
    character_list = []
    semantic_list = []

    if emotion and emotion.lower() not in ['unknown', 'neutral', 'none', '']:
        emotion_list.append(emotion.lower())
    if deep_emotions:
        deep_emo_list = deep_emotions.split(',') if isinstance(deep_emotions, str) else deep_emotions
        if isinstance(deep_emo_list, list):
            emotion_list.extend([e.strip().lower() for e in deep_emo_list if e and str(e).strip()])

    description_lower = description.lower() if description else ''
    emotion_keywords = ['joy', 'happy', 'sad', 'content', 'satisfaction', 'relief', 'confidence', 'pride', 'calm',
                       'trust', 'warm', 'camaraderie', 'friendship', 'bonding', 'triumphant', 'euphoric', 'sad',
                       'sadness', 'melancholy', 'tense', 'nervous', 'anxiety', 'fear', 'angry', 'frustration']
    for keyword in emotion_keywords:
        if keyword in description_lower and keyword not in emotion_list:
            emotion_list.append(keyword)

    laugh_keywords = {'laugh': 'warm-laugh', 'laughing': 'genuine-laugh', 'smile': 'warm-smile', 'smiling': 'content-smile'}
    for trigger, laugh_tag in laugh_keywords.items():
        if trigger in description_lower and laugh_tag not in laugh_list:
            laugh_list.append(laugh_tag)

    has_money = 'cash' in description_lower or 'money' in description_lower or 'stack' in description_lower
    if has_money:
        contextual_list.extend(['stack-of-cash', 'money-power', 'wealth-display', 'cash-aesthetic'])

    has_friendship = 'friend' in description_lower or 'duo' in description_lower or 'bond' in description_lower
    if has_friendship:
        contextual_list.extend(['friendship-moment', 'bonding-scene', 'camaraderie-display'])

    if actors:
        actors_str = str(actors)
        actors_list = actors_str.strip('[]').replace("'", "").split(',') if isinstance(actors, str) else actors
        if isinstance(actors_list, list):
            for actor in actors_list:
                if actor and str(actor).strip():
                    character_list.append(str(actor).strip().replace(' ', '-'))

    if series_movie and series_movie.lower() not in ['unknown', 'none', '']:
        semantic_list.append(series_movie.replace(' ', '-'))
    if media_type and media_type != 'Unknown':
        semantic_list.extend(['web-series', 'movie', 'film'] if 'Web' in media_type or 'Movie' in media_type else [])

    for tag in all_tags_list:
        tag_lower = tag.lower().strip()
        if not tag_lower:
            continue
        if any(w in tag_lower for w in ['joy', 'happy', 'sad', 'content']):
            if tag_lower not in emotion_list:
                emotion_list.append(tag_lower)
        elif 'laugh' in tag_lower or 'smile' in tag_lower:
            if tag_lower not in laugh_list:
                laugh_list.append(tag_lower)
        else:
            if tag_lower not in contextual_list:
                contextual_list.append(tag_lower)

    emotion_list = list(dict.fromkeys(emotion_list))
    laugh_list = list(dict.fromkeys(laugh_list))
    contextual_list = list(dict.fromkeys(contextual_list))
    character_list = list(dict.fromkeys(character_list))
    semantic_list = list(dict.fromkeys(semantic_list))

    return {
        'emotion_tags': ', '.join(emotion_list) if emotion_list else '',
        'laugh_tags': ', '.join(laugh_list) if laugh_list else '',
        'contextual_tags': ', '.join(contextual_list) if contextual_list else '',
        'character_tags': ', '.join(character_list) if character_list else '',
        'semantic_tags': ', '.join(semantic_list) if semantic_list else '',
        'total_count': len(emotion_list) + len(laugh_list) + len(contextual_list) + len(character_list) + len(semantic_list),
        'counts': {'emotion': len(emotion_list), 'laugh': len(laugh_list), 'contextual': len(contextual_list),
                   'character': len(character_list), 'semantic': len(semantic_list)}
    }


def analyze_frame_with_vision(frame_path, transcript_context='', filename_hint=''):
    """Analyze frame using OpenAI Vision API."""
    try:
        with open(frame_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')

        context_info = ""
        if transcript_context:
            context_info += f"\n\nDialogue/Transcript: {transcript_context}\n"
        if filename_hint:
            clean_hint = filename_hint.replace('_', ' ').replace('-', ' ').replace('.mp4', '').replace('.gif', '').replace('.mov', '')
            context_info += f"\nFilename Hint (may contain movie name): {clean_hint}\n"

        prompt = f"""You are an expert video analyst. Study this frame CAREFULLY and use ALL context clues.

CONTEXT CLUES PROVIDED:
{context_info}

CRITICAL: READ THE FILENAME CAREFULLY!
- If filename contains "Aamir_Khan" or "Aamir Khan" → AAMIR KHAN (plays Rancho in 3 Idiots)
- If filename contains "Kamyab_Nahi_Kabil" or "Kamyab Nahi Kabil" → 3 IDIOTS movie (famous dialogue)
- If filename contains "3_Idiots" or "3 Idiots" → 3 IDIOTS movie (Rancho/Aamir Khan, Farhan/R. Madhavan, Raju/Sharman Joshi)
- If filename contains "Farzi" → FARZI series (Sunny/Shahid Kapoor, Firoz/Bhuvan Arora)
- If filename contains "Scam_1992" or "Scam 1992" → SCAM 1992 series (Harshad Mehta/Pratik Gandhi)
- If filename contains "Shahid_Kapoor" or "Shahid Kapoor" → SHAHID KAPOOR (plays Sunny in Farzi)
- If filename contains "R_Madhavan" or "Madhavan" → R. MADHAVAN (plays Farhan in 3 Idiots)
- If filename contains "Highway" → HIGHWAY movie (Alia Bhatt, Randeep Hooda)
- If filename contains "Dil_Chahta_Hai" → DIL CHAHTA HAI movie
- If filename contains "Zindagi_Na_Milegi_Dobara" or "ZNMD" → ZNMD movie
- If transcript mentions character names → USE THOSE EXACT NAMES
- ALWAYS use character names from filename/transcript, NOT generic descriptions

STEP-BY-STEP VISUAL ANALYSIS:
1. LOOK CAREFULLY AT THE PEOPLE: How many? Gender? Ages? What are they DOING? Facial expressions?
2. LOOK FOR CONTEXT CLUES: Setting, objects, clothing, lighting
3. UNDERSTAND THE RELATIONSHIP & SCENE TYPE
4. IDENTIFY MOVIE/SERIES & CHARACTERS from filename first, then transcript

GENERATE DETAILED TAGS:

Visual Description (2-3 detailed sentences):
- WHO (use names from filename/transcript) + WHAT specific action + WHERE
- Facial expressions, emotions visible, body language
- Camera angle, lighting, setting atmosphere
- BE SPECIFIC: "Aamir Khan as Rancho teaches students" NOT "man talking"

Scene Summary (2-3 sentences): Emotional/narrative significance

Series/Movie: Name if you recognize it
Characters: Names from filename/transcript
Basic Emotion: sad/happy/laughing/crying/angry/surprised/fear/love/neutral

Emotion Tags (20-30 specific emotions)
Laugh Tags (CRITICAL - if ANY smiling/laughing - 10-15 types, empty [] if not)
Contextual Tags (20-30 scene context + COMMON SEARCHABLE TAGS)
Character Tags (15-25 - MANDATORY: Extract names from filename!)
Semantic Tags (25-40 visible details - DESCRIBE EVERYTHING)

Return ONLY valid JSON:
{{
  "visual_description": "2-3 detailed sentences: WHO + WHAT action + WHERE + facial expressions + body language + camera/lighting",
  "scene_summary": "2-3 sentences about emotional/narrative significance",
  "series_movie": "EXACT movie/series name from filename",
  "characters": "Character names from filename/transcript",
  "basic_emotion": "sad/happy/laughing/crying/angry/surprised/fear/love/neutral",
  "emotion_tags": ["20-30 specific emotion tags based on scene type"],
  "laugh_tags": ["10-15 laugh types if laughing, empty [] if not"],
  "contextual_tags": ["20-30 scene context: genre, setting, mood, relationships"],
  "character_tags": ["15-25 COMPREHENSIVE tags: actor names from filename, character names, relationships, roles"],
  "semantic_tags": ["25-40 visible details: actions, clothing, objects, setting, lighting, atmosphere, camera angle"]
}}

Return ONLY JSON, no other text."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}", "detail": "low"}}
                ]
            }],
            max_tokens=3000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.startswith('```'):
            lines = result_text.split('\n')[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            result_text = '\n'.join(lines).strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        result = json.loads(result_text)

        emotion_tags_list = result.get('emotion_tags', [])
        laugh_tags_list = result.get('laugh_tags', [])
        contextual_tags_list = result.get('contextual_tags', [])
        character_tags_list = result.get('character_tags', [])
        semantic_tags_list = result.get('semantic_tags', [])
        basic_emotion = result.get('basic_emotion', 'neutral')
        characters_str = result.get('characters', '')
        actor_name = ''
        if '(' in characters_str and ')' in characters_str:
            actor_name = characters_str.split('(')[1].split(')')[0].strip()
        elif ' as ' in characters_str:
            actor_name = characters_str.split(' as ')[0].strip()

        visual_desc = result.get('visual_description', '')
        scene_summary = result.get('scene_summary', '')
        full_description = f"[Visual - {basic_emotion.title()}] {visual_desc} {scene_summary}".strip()
        all_tags = character_tags_list + semantic_tags_list

        return {
            'description': full_description,
            'emotion': basic_emotion,
            'deep_emotions': ', '.join(emotion_tags_list),
            'ocr_text': '',
            'tags': ', '.join(all_tags),
            'genres': 'Drama',
            'scene_context': scene_summary,
            'people_description': characters_str,
            'actors': actor_name,
            'environment': visual_desc,
            'dialogue_context': transcript_context,
            'series_movie': result.get('series_movie', 'Unknown'),
            'media_type': 'Movie',
            'target_audience': 'General',
            'scene_type': 'dramatic',
            'emotion_tags': ', '.join(emotion_tags_list),
            'laugh_tags': ', '.join(laugh_tags_list),
            'contextual_tags': ', '.join(contextual_tags_list),
            'character_tags': ', '.join(character_tags_list),
            'semantic_tags': ', '.join(semantic_tags_list)
        }
    except Exception as e:
        print(f"❌ Error analyzing frame: {e}")
        return None


def extract_audio(video_path):
    """Extract audio from video using ffmpeg."""
    try:
        # Check multiple possible locations
        ffmpeg_paths = ['/opt/homebrew/bin/ffmpeg', '/usr/bin/ffmpeg', 'ffmpeg']
        ffprobe_paths = ['/opt/homebrew/bin/ffprobe', '/usr/bin/ffprobe', 'ffprobe']
        
        ffmpeg = None
        ffprobe = None
        
        for path in ffmpeg_paths:
            if os.path.exists(path) or path == 'ffmpeg':
                ffmpeg = path
                break
        for path in ffprobe_paths:
            if os.path.exists(path) or path == 'ffprobe':
                ffprobe = path
                break

        probe_cmd = [ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_type',
                     '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if not probe_result.stdout.strip():
            return None

        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        cmd = [ffmpeg, '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', '-y', audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("FFmpeg failed")
        return audio_path
    except Exception as e:
        print(f"❌ Error extracting audio: {e}")
        return None


def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper API."""
    with open(audio_path, 'rb') as audio_file:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="verbose_json")
    return transcript


def create_embedding(text):
    """Create embedding using OpenAI embeddings API."""
    response = client.embeddings.create(model='text-embedding-3-small', input=text)
    embedding = response.data[0].embedding
    return json.dumps(embedding).encode('utf-8')


def cosine_similarity(embedding1_blob, embedding2_blob):
    """Calculate cosine similarity between two embeddings."""
    try:
        vec1 = json.loads(embedding1_blob.decode('utf-8'))
        vec2 = json.loads(embedding2_blob.decode('utf-8'))
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
    except Exception:
        return 0.0


def upload_to_supabase_storage(local_path, remote_path, content_type=None):
    """Upload file to Supabase Storage."""
    import mimetypes
    with open(local_path, 'rb') as f:
        file_data = f.read()
    mime_type = content_type or mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
    supabase.storage.from_(BUCKET_NAME).upload(remote_path, file_data, file_options={"content-type": mime_type, "upsert": "true"})
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{remote_path}"


def process_video(video_path, filename):
    """Process video: upload to Supabase, transcribe, create embeddings, visual analysis."""
    print(f"\n{'='*60}\n🎬 PROCESSING VIDEO: {filename}\n{'='*60}")

    video_duration = get_video_duration(video_path)
    print(f"⏱️  Video duration: {video_duration:.2f}s")

    thumbnail_time = min(1.0, video_duration * 0.1)
    thumbnail_filename = f"thumb_{os.path.splitext(filename)[0]}.jpg"
    thumbnail_path = os.path.join(THUMBNAILS_FOLDER, thumbnail_filename)
    generate_thumbnail(video_path, thumbnail_path, thumbnail_time)

    video_remote_path = f"videos/{filename}"
    print("📤 Uploading video to Supabase Storage...")
    video_url = upload_to_supabase_storage(video_path, video_remote_path)
    print(f"✅ Video uploaded: {video_url}")

    thumbnail_remote_path = f"thumbnails/{thumbnail_filename}"
    if os.path.exists(thumbnail_path):
        thumbnail_url = upload_to_supabase_storage(thumbnail_path, thumbnail_remote_path, 'image/jpeg')
    else:
        thumbnail_url = None

    video_data = {
        'filename': filename,
        'duration': video_duration,
        'status': 'processing',
        'thumbnail': thumbnail_filename,
        'custom_tags': '',
        'supabase_video_url': video_url
    }
    result = supabase.table('videos').insert(video_data).execute()
    video_id = result.data[0]['id']
    print(f"✅ Video record created (ID: {video_id})")

    audio_path = extract_audio(video_path)
    segment_count = 0

    if audio_path:
        try:
            transcript = transcribe_audio(audio_path)
            for i, segment in enumerate(transcript.segments):
                start_time = segment.start
                end_time = segment.end
                text = segment.text.strip()
                if not text:
                    continue
                segment_count += 1
                clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
                combined_text = f"Title: {clean_title}. Transcript: {text}"
                embedding_blob = create_embedding(combined_text)
                embedding_list = json.loads(embedding_blob.decode('utf-8'))

                clip_data = {
                    'video_id': video_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'transcript_text': text,
                    'embedding': embedding_list,
                    'filename': filename,
                    'duration': min(CHUNK_DURATION, end_time - start_time)
                }
                try:
                    supabase.table('clips').insert(clip_data).execute()
                except Exception:
                    clip_data_no_emb = {k: v for k, v in clip_data.items() if k != 'embedding'}
                    supabase.table('clips').insert(clip_data_no_emb).execute()
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            print(f"⚠️  Audio transcription error: {e}")

    frames = extract_frames_for_analysis(video_path, video_duration, filename)

    transcript_resp = supabase.table('clips').select('transcript_text').eq('video_id', video_id).order('start_time').execute()
    full_transcript = ' '.join([r['transcript_text'] or '' for r in transcript_resp.data])

    visual_count = 0
    for frame_data in frames:
        nearby = supabase.table('clips').select('transcript_text').eq('video_id', video_id).lte('start_time', frame_data['timestamp'] + 10).gte('end_time', frame_data['timestamp'] - 10).order('start_time').limit(3).execute()
        context_transcript = ' '.join([r['transcript_text'] or '' for r in nearby.data])

        analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context_transcript, filename_hint=filename)
        if not analysis:
            continue

        def parse_tag_array(tag_data):
            if isinstance(tag_data, list):
                return ', '.join(str(t) for t in tag_data if t)
            return str(tag_data) if tag_data else ''

        description = str(analysis.get('description', ''))
        emotion = str(analysis.get('emotion', ''))
        ocr_text = str(analysis.get('ocr_text', ''))
        tags = str(analysis.get('tags', ''))
        genres = str(analysis.get('genres', ''))
        deep_emotions = str(analysis.get('deep_emotions', ''))
        scene_context = str(analysis.get('scene_context', ''))
        people_description = str(analysis.get('people_description', ''))
        environment = str(analysis.get('environment', ''))
        dialogue_context = str(analysis.get('dialogue_context', ''))
        series_movie = str(analysis.get('series_movie', ''))
        target_audience = str(analysis.get('target_audience', ''))
        scene_type = str(analysis.get('scene_type', ''))
        actors = str(analysis.get('actors', ''))
        media_type = str(analysis.get('media_type', 'Unknown'))

        emotion_tags = parse_tag_array(analysis.get('emotion_tags', ''))
        laugh_tags = parse_tag_array(analysis.get('laugh_tags', ''))
        contextual_tags = parse_tag_array(analysis.get('contextual_tags', ''))
        character_tags = parse_tag_array(analysis.get('character_tags', ''))
        semantic_tags = parse_tag_array(analysis.get('semantic_tags', ''))

        if not emotion_tags and not laugh_tags and not contextual_tags:
            generated = intelligently_generate_categorized_tags(analysis)
            emotion_tags = generated['emotion_tags']
            laugh_tags = generated['laugh_tags']
            contextual_tags = generated['contextual_tags']
            character_tags = generated['character_tags']
            semantic_tags = generated['semantic_tags']

        clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
        combined_text = f"Title: {clean_title}. {description}. Emotion: {emotion}."
        for fld, val in [('deep_emotions', deep_emotions), ('scene_context', scene_context), ('people_description', people_description),
                         ('environment', environment), ('series_movie', series_movie), ('emotion_tags', emotion_tags),
                         ('laugh_tags', laugh_tags), ('contextual_tags', contextual_tags), ('character_tags', character_tags),
                         ('semantic_tags', semantic_tags), ('genres', genres)]:
            if val:
                combined_text += f" {fld.replace('_', ' ').title()}: {val}."

        visual_embedding = create_embedding(combined_text)
        embedding_list = json.loads(visual_embedding.decode('utf-8'))

        frame_record = {
            'video_id': video_id,
            'filename': filename,
            'timestamp': frame_data['timestamp'],
            'visual_description': description,
            'emotion': emotion,
            'ocr_text': ocr_text,
            'tags': tags,
            'genres': genres,
            'deep_emotions': deep_emotions,
            'scene_context': scene_context,
            'people_description': people_description,
            'environment': environment,
            'dialogue_context': dialogue_context,
            'series_movie': series_movie,
            'target_audience': target_audience,
            'scene_type': scene_type,
            'actors': actors,
            'media_type': media_type,
            'emotion_tags': emotion_tags,
            'laugh_tags': laugh_tags,
            'contextual_tags': contextual_tags,
            'character_tags': character_tags,
            'semantic_tags': semantic_tags,
            'visual_embedding': embedding_list
        }
        try:
            supabase.table('visual_frames').insert(frame_record).execute()
        except Exception:
            frame_record.pop('visual_embedding', None)
            supabase.table('visual_frames').insert(frame_record).execute()
        visual_count += 1

    supabase.table('videos').update({'status': 'complete'}).eq('id', video_id).execute()
    print(f"✅ VIDEO PROCESSING COMPLETE! {segment_count} clips, {visual_count} visual frames")


@app.route('/')
def index():
    return send_from_directory('.', 'index_semantic.html')


@app.route('/index_semantic.html')
def index_semantic():
    return send_from_directory('.', 'index_semantic.html')


@app.route('/process_video/<int:video_id>', methods=['POST'])
def process_video_endpoint(video_id):
    """
    Process a video that's already uploaded to Supabase Storage
    Downloads from Supabase, runs AI analysis, uploads results
    """
    try:
        # Get video from database
        result = supabase.table('videos').select('*').eq('id', video_id).execute()
        if not result.data:
            return jsonify({'error': 'Video not found'}), 404
        
        video = result.data[0]
        filename = video['filename']
        video_url = video['supabase_video_url']
        
        # Download from Supabase Storage
        storage_path = f"videos/{filename}"
        video_data = supabase.storage.from_(BUCKET_NAME).download(storage_path)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(video_data)
            tmp_path = tmp.name
        
        try:
            # Run full AI processing
            process_video(tmp_path, filename)
            return jsonify({'success': True, 'message': 'Video processed successfully'})
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Quick upload endpoint - uploads video to Supabase Storage immediately,
    returns success, then processes in background
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Check if video already exists
        existing = supabase.table('videos').select('id').eq('filename', filename).execute()
        if existing.data:
            video_id = existing.data[0]['id']
            supabase.table('clips').delete().eq('video_id', video_id).execute()
            supabase.table('visual_frames').delete().eq('video_id', video_id).execute()
            supabase.table('videos').delete().eq('id', video_id).execute()

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            # Process video with full AI analysis
            print(f"🎬 Processing video: {filename}")
            process_video(tmp_path, filename)
            
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            
            # Return success
            return jsonify({
                'success': True, 
                'filename': filename,
                'message': 'Video processed successfully!'
            })
            
        except Exception as e:
            print(f"❌ Upload error: {str(e)}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid file type'}), 400


def _run_search(query, query_embedding, emotions_filter, genres_filter):
    """Core search logic - fetches from Supabase and computes similarity."""
    results = []
    detected_series = None
    detected_gender = None
    detected_count = None
    detected_actor = None
    detected_action = None
    detected_object = None

    if query:
        query_lower = query.lower()
        known_series = ['farzi', 'scam 1992', '3 idiots', 'highway', 'dil chahta hai', 'znmd', 'the office', 'breaking bad']
        for s in known_series:
            if s in query_lower:
                detected_series = s
                break

        known_actors = {'shahid': ['shahid kapoor', 'shahid'], 'aamir': ['aamir khan', 'aamir'], 'alia': ['alia bhatt', 'alia']}
        for k, v in known_actors.items():
            if k in query_lower:
                detected_actor = v
                break

    if not query and not emotions_filter and not genres_filter:
        return []

    v_resp = supabase.table('videos').select('id, filename, custom_tags').execute()
    v_map = {v['id']: v for v in v_resp.data}
    v_tags = {v['id']: v.get('custom_tags') or '' for v in v_resp.data}

    if not query and (emotions_filter or genres_filter):
        vf_resp = supabase.table('visual_frames').select('id, video_id, filename, timestamp, visual_description, emotion, ocr_text, tags, genres, deep_emotions, scene_context, people_description, environment, series_movie, actors, emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags').execute()

        for vf in vf_resp.data:
            vid = vf.get('video_id')
            custom_tags = v_tags.get(vid, '')
            fname = vf.get('filename') or (v_map.get(vid) or {}).get('filename', '')
            desc = vf.get('visual_description', '')
            emo = vf.get('emotion') or 'neutral'
            display = f"[Visual - {emo.title()}] {desc}" if emo != 'neutral' else f"[Visual] {desc}"
            if vf.get('ocr_text'):
                display += f" | Text: \"{vf['ocr_text']}\""
            results.append({
                'id': f"visual_{vf['id']}",
                'video_id': vid,
                'filename': fname,
                'timestamp': vf['timestamp'],
                'start_time': vf['timestamp'],
                'end_time': vf['timestamp'] + 10,
                'duration': 10.0,
                'text': display,
                'similarity': 1.0,
                'source': 'visual',
                'emotion': emo,
                'ocr_text': vf.get('ocr_text') or '',
                'tags': vf.get('tags') or '',
                'genres': vf.get('genres') or '',
                'custom_tags': custom_tags,
                'emotion_tags': vf.get('emotion_tags') or '',
                'laugh_tags': vf.get('laugh_tags') or '',
                'contextual_tags': vf.get('contextual_tags') or '',
                'character_tags': vf.get('character_tags') or '',
                'semantic_tags': vf.get('semantic_tags') or ''
            })
        return results

    clips_resp = supabase.table('clips').select('*').execute()
    vf_resp = supabase.table('visual_frames').select('*').execute()

    for clip in clips_resp.data:
        emb = clip.get('embedding')
        if not emb:
            continue
        emb_blob = json.dumps(emb).encode('utf-8')
        sim = cosine_similarity(query_embedding, emb_blob)
        text = clip.get('transcript_text', '')
        if query_lower and len(query_lower) > 3 and query_lower in text.lower():
            sim = min(1.0, sim + 0.35)
        if sim > 0.40:
            if text.strip() in ['♪', '♪♪', '[Music]', '(Music)'] and 'music' not in query.lower():
                continue
            clip_fname = clip.get('filename') or (v_map.get(clip['video_id']) or {}).get('filename', '')
            results.append({
                'id': f"audio_{clip['id']}",
                'video_id': clip['video_id'],
                'filename': clip_fname,
                'timestamp': clip['start_time'],
                'start_time': clip['start_time'],
                'end_time': clip['end_time'],
                'duration': clip.get('duration', clip['end_time'] - clip['start_time']),
                'text': text,
                'similarity': float(sim),
                'source': 'audio'
            })

    for vf in vf_resp.data:
        emb = vf.get('visual_embedding')
        if not emb:
            continue
        emb_blob = json.dumps(emb).encode('utf-8')
        sim = cosine_similarity(query_embedding, emb_blob)

        custom_tags = v_tags.get(vf['video_id'], '')
        desc = vf.get('visual_description', '')
        actors = vf.get('actors', '')
        series_movie = vf.get('series_movie', '')
        deep_emotions = vf.get('deep_emotions', '')
        ocr_text = vf.get('ocr_text', '')
        scene_context = vf.get('scene_context', '')
        tags = vf.get('tags', '')
        emotion_tags = vf.get('emotion_tags', '')
        laugh_tags = vf.get('laugh_tags', '')
        contextual_tags = vf.get('contextual_tags', '')
        character_tags = vf.get('character_tags', '')
        semantic_tags = vf.get('semantic_tags', '')

        exact_boost = 0.0
        if query and len(query_lower) > 2:
            if custom_tags and query_lower in custom_tags.lower():
                exact_boost = max(exact_boost, 0.50)
            if actors and query_lower in actors.lower():
                exact_boost = max(exact_boost, 0.45)
            if series_movie and query_lower in series_movie.lower():
                exact_boost = max(exact_boost, 0.40)
            if desc and query_lower in desc.lower():
                exact_boost = max(exact_boost, 0.35)
            for tag_fld in [emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags]:
                if tag_fld and query_lower.replace('-', ' ').replace('_', ' ') in tag_fld.lower().replace('-', ' ').replace('_', ' '):
                    exact_boost = max(exact_boost, 0.40)
                    break

        sim = min(1.0, sim + exact_boost)

        if detected_series and series_movie and detected_series not in (series_movie or '').lower():
            continue
        if detected_actor and actors:
            if not any(v in (actors or '').lower() for v in detected_actor):
                continue

        if sim > 0.30:
            emo = vf.get('emotion') or 'neutral'
            display = f"[Visual - {emo.title()}] {desc}" if emo != 'neutral' else f"[Visual] {desc}"
            if ocr_text:
                display += f" | Text: \"{ocr_text}\""
            vf_fname = vf.get('filename') or (v_map.get(vf['video_id']) or {}).get('filename', '')
            results.append({
                'id': f"visual_{vf['id']}",
                'video_id': vf['video_id'],
                'filename': vf_fname,
                'timestamp': vf['timestamp'],
                'start_time': vf['timestamp'],
                'end_time': vf['timestamp'] + 10,
                'duration': 10.0,
                'text': display,
                'similarity': float(sim),
                'source': 'visual',
                'emotion': emo,
                'ocr_text': ocr_text or '',
                'tags': tags or '',
                'genres': vf.get('genres') or '',
                'custom_tags': custom_tags or '',
                'emotion_tags': emotion_tags or '',
                'laugh_tags': laugh_tags or '',
                'contextual_tags': contextual_tags or '',
                'character_tags': character_tags or '',
                'semantic_tags': semantic_tags or ''
            })

    if emotions_filter or genres_filter:
        filtered = []
        for r in results:
            em_match = not emotions_filter or (r.get('emotion', 'neutral').lower() in [e.lower() for e in emotions_filter])
            genre_match = True
            if genres_filter and r.get('source') == 'visual':
                rg = (r.get('genres') or '').lower().split(', ')
                genre_match = any(g.lower() in rg for g in genres_filter)
            elif genres_filter and r.get('source') == 'audio':
                genre_match = False
            if em_match and genre_match:
                filtered.append(r)
        results = filtered

    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results


@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query', '').strip()
    emotions_filter = data.get('emotions', [])
    genres_filter = data.get('genres', [])

    if not query and not emotions_filter and not genres_filter:
        return jsonify({'results': []})

    try:
        query_embedding = None
        if query:
            query_embedding = create_embedding(query)

        results = _run_search(query, query_embedding, emotions_filter, genres_filter)

        if not results and query:
            return jsonify({
                'results': [],
                'message': f'No relevant B-rolls found for "{query}". Try different keywords or upload more videos.'
            })

        return jsonify({'results': results[:20]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/uploads/<path:filename>')
def serve_video(filename):
    """Redirect to Supabase Storage URL for video."""
    try:
        vid = supabase.table('videos').select('supabase_video_url').eq('filename', filename).execute()
        if vid.data and vid.data[0].get('supabase_video_url'):
            return redirect(vid.data[0]['supabase_video_url'])
    except Exception:
        pass
    url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/videos/{filename}"
    return redirect(url)


@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Redirect to Supabase Storage URL for thumbnail."""
    if filename.startswith('http'):
        return redirect(filename)
    url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/thumbnails/{filename}"
    return redirect(url)


@app.route('/videos', methods=['GET'])
def list_videos():
    try:
        v_resp = supabase.table('videos').select('id, filename, upload_date, duration, status, thumbnail, custom_tags, supabase_video_url').order('upload_date', desc=True).execute()
        c_resp = supabase.table('clips').select('video_id').execute()
        clip_counts = {}
        for c in c_resp.data:
            vid = c['video_id']
            clip_counts[vid] = clip_counts.get(vid, 0) + 1

        videos = []
        for v in v_resp.data:
            videos.append({
                'id': v['id'],
                'filename': v['filename'],
                'upload_date': v.get('upload_date'),
                'duration': v.get('duration'),
                'status': v.get('status', 'pending'),
                'thumbnail': v.get('thumbnail'),
                'custom_tags': v.get('custom_tags') or '',
                'clip_count': clip_counts.get(v['id'], 0),
                'supabase_video_url': v.get('supabase_video_url')
            })
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/reprocess/<int:video_id>', methods=['POST'])
def reprocess_video(video_id):
    try:
        v_resp = supabase.table('videos').select('filename, duration, supabase_video_url').eq('id', video_id).execute()
        if not v_resp.data:
            return jsonify({'error': 'Video not found'}), 404

        v = v_resp.data[0]
        filename = v['filename']
        video_duration = v['duration']
        video_url = v.get('supabase_video_url')

        supabase.table('visual_frames').delete().eq('video_id', video_id).execute()

        if not video_url:
            return jsonify({'error': 'Video file not found in storage'}), 404

        import urllib.request
        tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]).name
        try:
            urllib.request.urlretrieve(video_url, tmp_path)
        except Exception as e:
            return jsonify({'error': f'Failed to download video: {e}'}), 500

        frames = extract_frames_for_analysis(tmp_path, video_duration, filename)
        if not frames:
            os.remove(tmp_path)
            return jsonify({'error': 'Failed to extract frames'}), 500

        transcript_resp = supabase.table('clips').select('transcript_text').eq('video_id', video_id).order('start_time').execute()
        full_transcript = ' '.join([r['transcript_text'] or '' for r in transcript_resp.data])

        visual_count = 0
        for frame_data in frames:
            nearby = supabase.table('clips').select('transcript_text').eq('video_id', video_id).lte('start_time', frame_data['timestamp'] + 10).gte('end_time', frame_data['timestamp'] - 10).order('start_time').limit(3).execute()
            context = ' '.join([r['transcript_text'] or '' for r in nearby.data])

            analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context, filename_hint=filename)
            if not analysis:
                continue

            def parse_tag_array(tag_data):
                if isinstance(tag_data, list):
                    return ', '.join(str(t) for t in tag_data if t)
                return str(tag_data) if tag_data else ''

            emotion_tags = parse_tag_array(analysis.get('emotion_tags', ''))
            laugh_tags = parse_tag_array(analysis.get('laugh_tags', ''))
            contextual_tags = parse_tag_array(analysis.get('contextual_tags', ''))
            character_tags = parse_tag_array(analysis.get('character_tags', ''))
            semantic_tags = parse_tag_array(analysis.get('semantic_tags', ''))
            if not emotion_tags and not laugh_tags and not contextual_tags:
                gen = intelligently_generate_categorized_tags(analysis)
                emotion_tags, laugh_tags, contextual_tags = gen['emotion_tags'], gen['laugh_tags'], gen['contextual_tags']
                character_tags, semantic_tags = gen['character_tags'], gen['semantic_tags']

            desc = str(analysis.get('description', ''))
            clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
            combined = f"Title: {clean_title}. {desc}. Emotion: {analysis.get('emotion', '')}."
            for f, val in [('deep_emotions', analysis.get('deep_emotions')), ('scene_context', analysis.get('scene_context')), ('emotion_tags', emotion_tags), ('laugh_tags', laugh_tags), ('contextual_tags', contextual_tags), ('character_tags', character_tags), ('semantic_tags', semantic_tags)]:
                if val:
                    combined += f" {f}: {val}."
            emb = json.loads(create_embedding(combined).decode('utf-8'))

            frame_record = {
                'video_id': video_id,
                'filename': filename,
                'timestamp': frame_data['timestamp'],
                'visual_description': desc,
                'emotion': str(analysis.get('emotion', '')),
                'ocr_text': str(analysis.get('ocr_text', '')),
                'tags': str(analysis.get('tags', '')),
                'genres': str(analysis.get('genres', '')),
                'deep_emotions': str(analysis.get('deep_emotions', '')),
                'scene_context': str(analysis.get('scene_context', '')),
                'people_description': str(analysis.get('people_description', '')),
                'environment': str(analysis.get('environment', '')),
                'dialogue_context': str(analysis.get('dialogue_context', '')),
                'series_movie': str(analysis.get('series_movie', '')),
                'target_audience': str(analysis.get('target_audience', '')),
                'scene_type': str(analysis.get('scene_type', '')),
                'actors': str(analysis.get('actors', '')),
                'media_type': str(analysis.get('media_type', 'Unknown')),
                'emotion_tags': emotion_tags,
                'laugh_tags': laugh_tags,
                'contextual_tags': contextual_tags,
                'character_tags': character_tags,
                'semantic_tags': semantic_tags,
                'visual_embedding': emb
            }
            try:
                supabase.table('visual_frames').insert(frame_record).execute()
            except Exception:
                frame_record.pop('visual_embedding', None)
                supabase.table('visual_frames').insert(frame_record).execute()
            visual_count += 1

        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        return jsonify({'success': True, 'visual_frames_added': visual_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/filters', methods=['GET'])
def get_filters():
    try:
        vf = supabase.table('visual_frames').select('emotion, genres').execute()
        emotions = sorted(set(r['emotion'] for r in vf.data if r.get('emotion')))
        genres = set()
        for r in vf.data:
            for g in (r.get('genres') or '').split(', '):
                if g.strip():
                    genres.add(g.strip())
        return jsonify({'emotions': emotions, 'genres': sorted(list(genres))})
    except Exception:
        return jsonify({'emotions': [], 'genres': []})


@app.route('/videos/<int:video_id>/tags', methods=['POST'])
def add_custom_tag(video_id):
    data = request.json
    new_tag = data.get('tag', '').strip()
    if not new_tag:
        return jsonify({'error': 'Tag cannot be empty'}), 400

    v = supabase.table('videos').select('custom_tags').eq('id', video_id).execute()
    if not v.data:
        return jsonify({'error': 'Video not found'}), 404

    current = v.data[0].get('custom_tags') or ''
    tags_list = [t.strip() for t in current.split(',') if t.strip()]
    if new_tag.lower() in [t.lower() for t in tags_list]:
        return jsonify({'error': 'Tag already exists', 'tags': ', '.join(tags_list)}), 400

    tags_list.append(new_tag)
    updated = ', '.join(tags_list)
    supabase.table('videos').update({'custom_tags': updated}).eq('id', video_id).execute()
    return jsonify({'success': True, 'tag': new_tag, 'all_tags': updated})


@app.route('/videos/<int:video_id>/tags/<path:tag>', methods=['DELETE'])
def delete_custom_tag(video_id, tag):
    v = supabase.table('videos').select('custom_tags').eq('id', video_id).execute()
    if not v.data:
        return jsonify({'error': 'Video not found'}), 404

    current = v.data[0].get('custom_tags') or ''
    tags_list = [t.strip() for t in current.split(',') if t.strip()]
    tags_list = [t for t in tags_list if t.lower() != tag.lower()]
    updated = ', '.join(tags_list)
    supabase.table('videos').update({'custom_tags': updated}).eq('id', video_id).execute()
    return jsonify({'success': True, 'deleted_tag': tag, 'remaining_tags': updated})


@app.route('/delete/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    try:
        v = supabase.table('videos').select('filename, thumbnail').eq('id', video_id).execute()
        if not v.data:
            return jsonify({'error': 'Video not found'}), 404

        filename = v.data[0]['filename']
        supabase.table('clips').delete().eq('video_id', video_id).execute()
        supabase.table('visual_frames').delete().eq('video_id', video_id).execute()
        supabase.table('videos').delete().eq('id', video_id).execute()

        try:
            supabase.storage.from_(BUCKET_NAME).remove([f"videos/{filename}"])
        except Exception:
            pass
        thumb_name = f"thumb_{os.path.splitext(filename)[0]}.jpg"
        try:
            supabase.storage.from_(BUCKET_NAME).remove([f"thumbnails/{thumb_name}"])
        except Exception:
            pass

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 B-ROLL MAPPER - SUPABASE VERSION")
    print("="*60)
    print("✅ Supabase PostgreSQL + Storage")
    print("✅ OpenAI Whisper, Vision, Embeddings")
    print("✅ Server: http://localhost:5002")
    print("="*60 + "\n")
    app.run(debug=False, port=5002)
