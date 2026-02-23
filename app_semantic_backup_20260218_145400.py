import os
import sqlite3
import subprocess
import math
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
import tempfile
import json
from pathlib import Path
import google.generativeai as genai
from PIL import Image

# Import Gemini analyzer
from gemini_analyzer import analyze_frame_with_gemini

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY and GEMINI_API_KEY != 'YOUR_GEMINI_API_KEY_HERE':
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API configured for visual analysis")
else:
    print("⚠️  Warning: No Gemini API key found - visual analysis will fail")

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
THUMBNAILS_FOLDER = 'thumbnails'
FRAMES_FOLDER = 'frames'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'gif'}
DATABASE = 'broll_semantic.db'
CHUNK_DURATION = 15  # 15-second chunks
FRAME_INTERVAL = 10  # Extract 1 frame every 10 seconds for visual analysis

# SQLite connection helper with timeout
def get_db_connection():
    """Get SQLite connection with proper timeout to prevent locking."""
    conn = sqlite3.connect(DATABASE, timeout=30.0, isolation_level='DEFERRED')
    conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
    return conn

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAILS_FOLDER, exist_ok=True)
os.makedirs(FRAMES_FOLDER, exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Database initialization
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency (prevents database locked errors)
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
    
    # Videos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration REAL NOT NULL,
            status TEXT DEFAULT 'processing',
            thumbnail TEXT,
            custom_tags TEXT DEFAULT ''
        )
    ''')
    
    # Clips table with audio embeddings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            duration REAL NOT NULL,
            transcript_text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')
    
    # Visual analysis table for multi-modal search with emotions, OCR, genres, and advanced tagging
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visual_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            timestamp REAL NOT NULL,
            frame_path TEXT NOT NULL,
            visual_description TEXT NOT NULL,
            visual_embedding BLOB NOT NULL,
            emotion TEXT,
            ocr_text TEXT,
            tags TEXT,
            genres TEXT,
            deep_emotions TEXT,
            scene_context TEXT,
            people_description TEXT,
            environment TEXT,
            dialogue_context TEXT,
            series_movie TEXT,
            target_audience TEXT,
            scene_type TEXT,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')
    
    # Add new columns to visual_frames if they don't exist (migration)
    cursor.execute("PRAGMA table_info(visual_frames)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'emotion' not in columns:
        print("🔄 Adding 'emotion' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN emotion TEXT')
    
    if 'ocr_text' not in columns:
        print("🔄 Adding 'ocr_text' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN ocr_text TEXT')
    
    if 'tags' not in columns:
        print("🔄 Adding 'tags' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN tags TEXT')
    
    if 'genres' not in columns:
        print("🔄 Adding 'genres' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN genres TEXT')
    
    # Add actors and media_type columns
    if 'actors' not in columns:
        print("🔄 Adding 'actors' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN actors TEXT')
    
    if 'media_type' not in columns:
        print("🔄 Adding 'media_type' column to visual_frames...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN media_type TEXT')
    
    # Add new advanced tagging columns
    if 'deep_emotions' not in columns:
        print("🔄 Adding 'deep_emotions' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN deep_emotions TEXT')
    
    if 'scene_context' not in columns:
        print("🔄 Adding 'scene_context' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN scene_context TEXT')
    
    if 'people_description' not in columns:
        print("🔄 Adding 'people_description' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN people_description TEXT')
    
    if 'environment' not in columns:
        print("🔄 Adding 'environment' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN environment TEXT')
    
    if 'dialogue_context' not in columns:
        print("🔄 Adding 'dialogue_context' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN dialogue_context TEXT')
    
    if 'series_movie' not in columns:
        print("🔄 Adding 'series_movie' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN series_movie TEXT')
    
    if 'target_audience' not in columns:
        print("🔄 Adding 'target_audience' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN target_audience TEXT')
    
    if 'scene_type' not in columns:
        print("🔄 Adding 'scene_type' column for advanced tagging...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN scene_type TEXT')
    
    if 'actors' not in columns:
        print("🔄 Adding 'actors' column for actor recognition...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN actors TEXT')
    
    if 'media_type' not in columns:
        print("🔄 Adding 'media_type' column (Movie/Series/TV/Ad)...")
        cursor.execute('ALTER TABLE visual_frames ADD COLUMN media_type TEXT')
    
    # Add custom_tags column to videos table for user-added tags
    cursor.execute("PRAGMA table_info(videos)")
    video_columns = [col[1] for col in cursor.fetchall()]
    
    if 'custom_tags' not in video_columns:
        print("🔄 Adding 'custom_tags' column to videos table for user tags...")
        cursor.execute("ALTER TABLE videos ADD COLUMN custom_tags TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

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
        print(f"❌ Error getting video duration: {e}")
        return 0

def generate_thumbnail(video_path, thumbnail_path, timestamp=1.0):
    """Generate video thumbnail using ffmpeg at specific timestamp."""
    try:
        print(f"🖼️  Generating thumbnail at {timestamp}s...")
        cmd = [
            '/opt/homebrew/bin/ffmpeg',
            '-i', video_path,
            '-ss', str(timestamp),  # Seek to timestamp
            '-vframes', '1',  # Extract 1 frame
            '-q:v', '2',  # High quality
            '-y',  # Overwrite
            thumbnail_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFmpeg thumbnail error: {result.stderr}")
            raise Exception(f"Thumbnail generation failed with code {result.returncode}")
        
        print(f"✅ Thumbnail generated: {thumbnail_path}")
        return thumbnail_path
    except Exception as e:
        print(f"❌ Error generating thumbnail: {e}")
        return None

def extract_frames_for_analysis(video_path, video_duration, filename):
    """Extract frames at regular intervals for visual analysis."""
    try:
        frames = []
        video_base = os.path.splitext(filename)[0]
        is_gif = filename.lower().endswith('.gif')
        
        # For GIFs and short videos, extract MORE frames to capture text better
        if is_gif or video_duration < 30:
            # Short content: Extract every 2 seconds OR at least 5 frames
            interval = min(2, video_duration / 5) if video_duration > 10 else max(1, video_duration / 3)
            num_frames = max(3, int(video_duration / interval))
            print(f"🎞️  Extracting {num_frames} frames (SHORT/GIF mode - every {interval:.1f}s)...")
        else:
            # Long content: Use standard interval
            interval = FRAME_INTERVAL
            num_frames = max(1, int(video_duration / interval))
            print(f"🎞️  Extracting {num_frames} frames (standard mode - every {interval}s)...")
        
        for i in range(num_frames):
            timestamp = i * interval
            if timestamp >= video_duration:
                break
                
            frame_filename = f"{video_base}_frame_{int(timestamp)}s.jpg"
            frame_path = os.path.join(FRAMES_FOLDER, frame_filename)
            
            cmd = [
                '/opt/homebrew/bin/ffmpeg',
                '-ss', str(timestamp),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                frame_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                frames.append({
                    'timestamp': timestamp,
                    'path': frame_path,
                    'filename': frame_filename
                })
                print(f"   ✅ Frame at {timestamp}s extracted")
            else:
                print(f"   ⚠️  Failed to extract frame at {timestamp}s")
        
        print(f"✅ Extracted {len(frames)} frames successfully")
        return frames
        
    except Exception as e:
        print(f"❌ Error extracting frames: {e}")
        return []

def extract_text_with_tesseract(frame_path):
    """Extract text using Tesseract OCR with image pre-processing for stylized text."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import pytesseract
        
        image = Image.open(frame_path)
        
        # Try multiple OCR approaches for best results
        ocr_results = []
        
        # Approach 1: Original image with aggressive config
        text1 = pytesseract.image_to_string(image, config='--psm 11 --oem 3').strip()
        if text1 and len(text1) > 3:
            ocr_results.append(text1)
        
        # Approach 2: Enhance contrast for bold text
        enhancer = ImageEnhance.Contrast(image)
        img_enhanced = enhancer.enhance(2.0)
        text2 = pytesseract.image_to_string(img_enhanced, config='--psm 6 --oem 3').strip()
        if text2 and len(text2) > 3:
            ocr_results.append(text2)
        
        # Approach 3: Grayscale for better text detection
        img_gray = ImageOps.grayscale(image)
        text3 = pytesseract.image_to_string(img_gray, config='--psm 11 --oem 3').strip()
        if text3 and len(text3) > 3:
            ocr_results.append(text3)
        
        # Approach 4: High contrast binary (black/white)
        img_bw = img_gray.point(lambda x: 0 if x < 128 else 255, '1')
        text4 = pytesseract.image_to_string(img_bw, config='--psm 6').strip()
        if text4 and len(text4) > 3:
            ocr_results.append(text4)
        
        # Return longest result (most likely to be accurate)
        if ocr_results:
            best_result = max(ocr_results, key=len)
            return best_result
        
        return ""
    except Exception as e:
        print(f"        ⚠️  Tesseract OCR failed: {e}")
        return ""


def intelligently_generate_categorized_tags(analysis):
    """
    INTELLIGENTLY GENERATE comprehensive categorized tags from Vision API analysis.
    This expands beyond just the 'tags' field to extract tags from description, emotion,
    scene_context, environment, actors, and other rich metadata.
    Returns: dict with 'emotion_tags', 'laugh_tags', 'contextual_tags', 'character_tags', 'semantic_tags' (all as comma-separated strings)
    """
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
    
    # Extract existing tags from 'tags' field
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
    
    # ===== A. EMOTION TAGS from multiple sources =====
    # From 'emotion' field
    if emotion and emotion.lower() not in ['unknown', 'neutral', 'none', '']:
        emotion_list.append(emotion.lower())
    
    # From 'deep_emotions' array
    if deep_emotions:
        deep_emo_list = deep_emotions.split(',') if isinstance(deep_emotions, str) else deep_emotions
        if isinstance(deep_emo_list, list):
            emotion_list.extend([e.strip().lower() for e in deep_emo_list if e and str(e).strip()])
    
    # From description - extract emotion words
    description_lower = description.lower() if description else ''
    emotion_keywords = ['joy', 'happy', 'happiness', 'content', 'contentment', 'satisfaction', 'satisfied',
                       'relief', 'relieved', 'confidence', 'confident', 'pride', 'proud', 'calm', 'trust',
                       'trusting', 'warm', 'camaraderie', 'friendship', 'bonding', 'bond', 'triumphant',
                       'euphoric', 'ecstatic', 'victorious', 'genuine', 'authentic', 'relaxed', 'comfortable',
                       'pleased', 'cheerful', 'positive', 'peaceful', 'ease', 'gratitude', 'grateful',
                       'sad', 'sadness', 'melancholy', 'tense', 'tension', 'nervous', 'anxiety', 'anxious',
                       'fear', 'fearful', 'scared', 'angry', 'anger', 'rage', 'frustration', 'frustrated',
                       'sarcasm', 'sarcastic', 'mocking', 'derisive', 'contemptuous', 'manipulative', 'sinister',
                       'evil', 'menacing', 'threatening', 'intimidating', 'dominant', 'power', 'control']
    for keyword in emotion_keywords:
        if keyword in description_lower and keyword not in emotion_list:
            emotion_list.append(keyword)
    
    # From scene_context
    scene_lower = scene_context.lower() if scene_context else ''
    if 'celebration' in scene_lower:
        for tag in ['celebratory', 'victory', 'success', 'achievement']:
            if tag not in emotion_list:
                emotion_list.append(tag)
    if 'triumph' in scene_lower:
        for tag in ['triumphant', 'victorious', 'proud']:
            if tag not in emotion_list:
                emotion_list.append(tag)
    if 'conflict' in scene_lower or 'confrontation' in scene_lower:
        for tag in ['tense', 'conflict', 'confrontational']:
            if tag not in emotion_list:
                emotion_list.append(tag)
    
    # ===== B. LAUGH TAGS - detect from description =====
    laugh_keywords = {
        'laugh': 'warm-laugh', 'laughing': 'genuine-laugh', 'smile': 'warm-smile',
        'smiling': 'content-smile', 'grin': 'happy-grin', 'chuckle': 'friendly-chuckle',
        'hearty': 'hearty-laugh', 'warm': 'warm-laugh', 'genuine': 'genuine-laugh',
        'maniacal': 'maniacal-laugh', 'wild': 'wild-laugh', 'delirious': 'delirious-laugh',
        'relieved': 'relieved-laugh', 'satisfied': 'satisfied-laugh', 'shared': 'shared-laugh'
    }
    for trigger, laugh_tag in laugh_keywords.items():
        if trigger in description_lower and laugh_tag not in laugh_list:
            laugh_list.append(laugh_tag)
    
    # ===== C. CONTEXTUAL TAGS from environment + scene_context + description =====
    
    # NARRATIVE CONTEXT LAYER: Add story-based tags based on series + visual combinations
    series_lower = series_movie.lower() if series_movie else ''
    
    # Crime/Heist shows with money = add crime/heist narrative tags
    crime_shows = ['farzi', 'scam', 'mirzapur', 'sacred games', 'money heist', 'paatal lok', 'jamtara']
    has_money = 'cash' in description_lower or 'money' in description_lower or 'stack' in description_lower or 'bundle' in description_lower or 'currency' in description_lower
    is_crime_show = any(show in series_lower for show in crime_shows)
    
    if is_crime_show and has_money:
        # Add crime/heist narrative tags
        narrative_tags = [
            'crime-comedy', 'heist-moment', 'illegal-money', 'criminal-success',
            'financial-rebellion', 'underground-wealth', 'illicit-cash',
            'money-montage', 'cash-celebration', 'criminal-victory',
            'illegal-jackpot', 'heist-aftermath', 'crime-triumph',
            'forbidden-wealth', 'unlawful-riches', 'con-artist-win',
            'greed-aesthetic', 'dirty-money', 'outlaw-riches', 'criminal-wealth',
            'heist-success', 'con-victory', 'scam-payoff'
        ]
        for tag in narrative_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        # Also upgrade emotion tags to match crime context
        crime_emotions = [
            'rebellious', 'triumphant', 'victorious', 'power-high', 'wild-success', 'mad-joy',
            'euphoric', 'ecstatic', 'disbelief', 'money-intoxication', 'adrenaline-rush',
            'criminal-thrill', 'forbidden-joy', 'reckless-happiness', 'chaos-energy'
        ]
        for tag in crime_emotions:
            if tag not in emotion_list:
                emotion_list.append(tag)
        
        # Upgrade laugh tags for crime celebration
        crime_laughs = [
            'criminal-success-laugh', 'we-did-it-laugh', 'rich-laugh', 'broke-no-more-laugh',
            'illegal-jackpot-laugh', 'delirious-laugh', 'maniacal-laugh', 'unhinged-joy',
            'dark-comedy-laugh', 'boys-gone-rogue-laugh', 'villainous-laugh', 'mischief-laugh',
            'crazy-cash-laugh', 'heist-celebration-laugh'
        ]
        for tag in crime_laughs:
            if tag not in laugh_list:
                laugh_list.append(tag)
    
    # Stack of cash = wealth/power narrative (regardless of series)
    if has_money:
        wealth_tags = [
            'stack-of-cash', 'money-power', 'wealth-display', 'cash-aesthetic',
            'money-success', 'financial-breakthrough', 'currency-stack',
            'bundled-money', 'paper-bills', 'cash-bundles'
        ]
        for tag in wealth_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # Friendship/duo + money = add bromance/partnership narrative
    has_friendship = 'friend' in description_lower or 'duo' in description_lower or 'two men' in description_lower or 'two women' in description_lower or 'partnership' in description_lower
    if has_friendship and has_money:
        friendship_tags = [
            'bromance-moment', 'partnership-success', 'shared-victory', 'duo-celebration',
            'friends-winning', 'bonded-triumph', 'partner-in-crime', 'dynamic-duo'
        ]
        for tag in friendship_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        # If crime show + friendship + money = add chaos/madness tags
        if is_crime_show:
            chaos_tags = [
                'friendship-x-madness', 'bromance-chaos', 'partners-in-chaos',
                'duo-mayhem', 'bonded-mischief', 'chaotic-partnership',
                'wild-bromance', 'reckless-friends', 'boys-gone-wild'
            ]
            for tag in chaos_tags:
                if tag not in contextual_list:
                    contextual_list.append(tag)
    
    # Underground/dim/industrial + money = add underground lair aesthetic
    has_underground = 'underground' in description_lower or 'dim' in description_lower or 'industrial' in description_lower or 'vault' in description_lower
    if has_underground and has_money:
        underground_tags = ['underground-lair', 'vault-aesthetic', 'secret-hideout', 'hidden-wealth', 'dimly-lit-cash', 'industrial-money-room']
        for tag in underground_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # ===== UNIVERSAL NARRATIVE CONTEXTS (for ALL genres, not just crime) =====
    
    # COMEDY/HUMOR scenes
    # IMPORTANT: Only add comedy tags if scene is ACTUALLY funny (not just because movie is a comedy)
    has_comedy_keywords = 'playful' in description_lower or 'funny' in description_lower or 'humor' in description_lower or 'laugh' in description_lower or 'joke' in description_lower or 'comedic' in description_lower or 'amusing' in description_lower
    
    # Check if scene is EMOTIONAL/DRAMATIC (opposite of comedy)
    is_emotional_scene = any(word in description_lower for word in ['grief', 'sorrow', 'sad', 'cry', 'tears', 'emotional', 'heartbreak', 'anguish', 'distress', 'despair', 'devastat', 'tragic', 'painful'])
    
    # Only add comedy tags if scene has comedy keywords AND is NOT an emotional/dramatic scene
    if has_comedy_keywords and not is_emotional_scene:
        comedy_tags = [
            'comedy-scene', 'humorous-moment', 'lighthearted', 'fun-vibes',
            'playful-banter', 'comic-relief', 'funny-interaction', 'amusing-scene',
            'laughter-moment', 'comedic-timing', 'witty-exchange', 'jovial-atmosphere'
        ]
        for tag in comedy_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        # Add comedy-specific emotions
        comedy_emotions = ['playful-joy', 'amusement', 'cheerfulness', 'lighthearted', 'glee', 'merriment']
        for tag in comedy_emotions:
            if tag not in emotion_list:
                emotion_list.append(tag)
        
        # Add comedy laughs
        comedy_laughs = ['jovial-laugh', 'playful-laugh', 'comedic-laugh', 'fun-laugh', 'lighthearted-chuckle']
        for tag in comedy_laughs:
            if tag not in laugh_list:
                laugh_list.append(tag)
    
    # FRIENDSHIP/BONDING scenes (very common!)
    has_bonding = has_friendship or 'bond' in description_lower or 'camaraderie' in description_lower or 'brother' in description_lower or 'together' in description_lower or 'group' in description_lower
    if has_bonding and not has_money:  # If no money (already covered above)
        bonding_tags = [
            'friendship-moment', 'bonding-scene', 'camaraderie-display', 'brotherhood-vibes',
            'companionship', 'togetherness', 'group-bonding', 'social-connection',
            'male-bonding', 'buddy-moment', 'friend-zone', 'team-spirit',
            'unity', 'solidarity', 'kinship', 'fellowship'
        ]
        for tag in bonding_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        # Add friendship emotions
        bonding_emotions = ['camaraderie', 'trust', 'loyalty', 'affection', 'kinship', 'companionship']
        for tag in bonding_emotions:
            if tag not in emotion_list:
                emotion_list.append(tag)
    
    # COLLEGE/STUDENT scenes
    # IMPORTANT: Only add college tags if ACTUALLY a college scene (not just because movie is about college)
    has_college_setting = 'college' in description_lower or 'campus' in description_lower or 'student' in description_lower or 'hostel' in description_lower or 'classroom' in description_lower or 'university' in description_lower or 'dorm' in description_lower or 'lecture' in description_lower or 'exam' in description_lower
    
    # DON'T assume all scenes from college movies are college scenes!
    # Check if it's actually IN a college setting (not a family/home scene)
    is_family_scene = 'family' in description_lower or 'home' in description_lower or 'domestic' in description_lower or 'parent' in description_lower or 'father' in description_lower or 'mother' in description_lower
    
    # Only add college tags if it's actually a college setting AND not a family scene
    if has_college_setting and not is_family_scene:
        college_tags = [
            'college-life', 'campus-scene', 'student-vibes', 'hostel-moment',
            'college-friendship', 'university-setting', 'academic-environment',
            'youthful-energy', 'campus-bonding', 'dorm-life', 'educational-setting'
        ]
        # Only add 'college-comedy' if scene is actually funny/lighthearted
        if any(word in description_lower for word in ['laugh', 'funny', 'comic', 'playful', 'humorous', 'joke']):
            college_tags.extend(['college-comedy', 'student-hijinks'])
        
        for tag in college_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # ROMANCE/LOVE scenes
    has_romance = 'romantic' in description_lower or 'love' in description_lower or 'kiss' in description_lower or 'embrace' in description_lower or 'couple' in description_lower or 'intimate' in description_lower
    if has_romance:
        romance_tags = [
            'romantic-moment', 'love-scene', 'intimate-moment', 'tender-exchange',
            'romantic-chemistry', 'affectionate-scene', 'couple-moment', 'romance-vibes',
            'emotional-connection', 'heartfelt-interaction'
        ]
        for tag in romance_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        romance_emotions = ['romantic', 'affection', 'tenderness', 'intimacy', 'love', 'passion']
        for tag in romance_emotions:
            if tag not in emotion_list:
                emotion_list.append(tag)
    
    # ACTION/FIGHT scenes
    has_action = 'fight' in description_lower or 'action' in description_lower or 'chase' in description_lower or 'running' in description_lower or 'punch' in description_lower or 'weapon' in description_lower
    if has_action:
        action_tags = [
            'action-scene', 'intense-moment', 'adrenaline', 'dynamic-action',
            'fight-sequence', 'chase-scene', 'high-energy', 'physical-action',
            'combat', 'confrontation-scene'
        ]
        for tag in action_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
        
        action_emotions = ['intense', 'adrenaline', 'focused', 'determined', 'aggressive']
        for tag in action_emotions:
            if tag not in emotion_list:
                emotion_list.append(tag)
    
    # DRAMATIC/EMOTIONAL scenes
    has_drama = 'dramatic' in description_lower or 'emotional' in description_lower or 'tear' in description_lower or 'cry' in description_lower or 'intense' in description_lower
    if has_drama:
        drama_tags = [
            'dramatic-scene', 'emotional-moment', 'intense-drama', 'powerful-scene',
            'emotional-depth', 'dramatic-tension', 'heartfelt-moment', 'serious-tone'
        ]
        for tag in drama_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # FAMILY scenes
    has_family = 'family' in description_lower or 'parent' in description_lower or 'father' in description_lower or 'mother' in description_lower or 'child' in description_lower or 'sibling' in description_lower
    if has_family:
        family_tags = [
            'family-moment', 'domestic-scene', 'family-bonding', 'parental-interaction',
            'familial-love', 'household-scene', 'family-dynamics'
        ]
        for tag in family_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # WORKPLACE/OFFICE scenes
    has_workplace = 'office' in description_lower or 'workplace' in description_lower or 'corporate' in description_lower or 'meeting' in description_lower or 'desk' in description_lower
    if has_workplace:
        workplace_tags = [
            'office-scene', 'workplace-moment', 'corporate-setting', 'professional-environment',
            'work-vibes', 'business-scene', 'office-culture', 'workplace-interaction'
        ]
        for tag in workplace_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # CELEBRATION/PARTY scenes
    has_celebration = 'celebrat' in description_lower or 'party' in description_lower or 'toast' in description_lower or 'cheer' in description_lower or 'victory' in description_lower
    if has_celebration and not has_money:  # If no money (already covered)
        celebration_tags = [
            'celebration-scene', 'party-vibes', 'festive-moment', 'victory-celebration',
            'joyful-gathering', 'group-celebration', 'triumph-moment', 'success-party'
        ]
        for tag in celebration_tags:
            if tag not in contextual_list:
                contextual_list.append(tag)
    
    # From environment field (EXPANDED for all settings)
    if environment:
        env_lower = environment.lower()
        contextual_keywords = {
            # Money/Wealth
            'money': ['money', 'cash', 'currency', 'wealth-display'],
            'cash': ['money', 'cash', 'currency', 'wealth-display'],
            'stack': ['stack-of-cash', 'bundled-money', 'cash-stack'],
            # Lighting
            'lighting': ['dramatic-lighting'],
            'light': ['dramatic-lighting', 'illumination'],
            'dim': ['dim-lighting', 'dim-atmosphere', 'low-light'],
            'bright': ['bright-lighting', 'well-lit', 'luminous'],
            'natural': ['natural-lighting', 'daylight'],
            'neon': ['neon-lighting', 'neon-aesthetic'],
            # Settings
            'industrial': ['industrial-setting', 'industrial-aesthetic'],
            'modern': ['modern-interior', 'modern-aesthetic', 'contemporary'],
            'underground': ['underground-setting'],
            'office': ['office-setting', 'workplace', 'corporate-space'],
            'outdoor': ['outdoor-setting', 'exterior', 'outside'],
            'indoor': ['indoor-setting', 'interior'],
            'luxury': ['luxury-setting', 'upscale-environment', 'high-end'],
            # Specific Rooms
            'bathroom': ['bathroom-scene', 'washroom', 'restroom-setting'],
            'bedroom': ['bedroom-scene', 'sleeping-quarters'],
            'kitchen': ['kitchen-setting', 'cooking-area'],
            'living room': ['living-room', 'common-area'],
            'hallway': ['hallway-scene', 'corridor'],
            'classroom': ['classroom-setting', 'educational-space'],
            'restaurant': ['restaurant-setting', 'dining-scene'],
            'bar': ['bar-setting', 'pub-scene', 'drinking-establishment'],
            'cafe': ['cafe-setting', 'coffee-shop'],
            'street': ['street-scene', 'urban-street', 'road-setting'],
            'park': ['park-setting', 'outdoor-park'],
            'car': ['car-scene', 'vehicle-interior'],
            # Atmosphere
            'busy': ['busy-environment', 'crowded', 'active-scene'],
            'quiet': ['quiet-atmosphere', 'peaceful-setting'],
            'chaotic': ['chaotic-environment', 'hectic-scene'],
            'intimate': ['intimate-setting', 'private-space'],
            'public': ['public-space', 'open-area'],
            # Time of day
            'morning': ['morning-scene', 'am-time', 'early-hours'],
            'night': ['night-scene', 'evening-time', 'after-dark'],
            'day': ['daytime-scene', 'daylight-hours']
        }
        for keyword, tags_to_add in contextual_keywords.items():
            if keyword in env_lower:
                for tag in tags_to_add:
                    if tag not in contextual_list:
                        contextual_list.append(tag)
    
    # From scene_context (EXPANDED)
    if scene_context:
        scene_words = scene_context.lower()
        if 'money' in scene_words or 'financial' in scene_words:
            for tag in ['financial-success', 'money-power', 'wealth']:
                if tag not in contextual_list:
                    contextual_list.append(tag)
        if 'success' in scene_words or 'achievement' in scene_words:
            for tag in ['success-moment', 'achievement', 'milestone']:
                if tag not in contextual_list:
                    contextual_list.append(tag)
        if 'celebration' in scene_words or 'victory' in scene_words:
            for tag in ['celebration', 'victory-moment', 'shared-victory']:
                if tag not in contextual_list:
                    contextual_list.append(tag)
        if 'calm' in scene_words:
            contextual_list.append('calm-atmosphere')
    
    # Extract ACTIVITIES/ACTIONS from description
    activity_keywords = {
        # Daily routines
        'brushing': ['brushing-teeth', 'grooming', 'morning-routine', 'hygiene'],
        'washing': ['washing', 'cleaning', 'hygiene-routine'],
        'eating': ['eating', 'dining', 'meal-time'],
        'drinking': ['drinking', 'beverage-consumption'],
        'cooking': ['cooking', 'food-preparation'],
        'sleeping': ['sleeping', 'resting', 'bedtime'],
        # Social activities
        'talking': ['conversation', 'dialogue', 'verbal-exchange'],
        'laughing': ['laughter', 'jovial-moment', 'humorous-exchange'],
        'smiling': ['smiling', 'positive-expression'],
        'hugging': ['embrace', 'physical-affection', 'hug'],
        'shaking hands': ['handshake', 'greeting', 'formal-greeting'],
        # Work/Study activities
        'working': ['working', 'productivity', 'task-execution'],
        'typing': ['typing', 'computer-work', 'keyboard-use'],
        'reading': ['reading', 'studying', 'book-reading'],
        'writing': ['writing', 'documentation', 'note-taking'],
        'studying': ['studying', 'learning', 'academic-work'],
        # Physical activities
        'walking': ['walking', 'movement', 'locomotion'],
        'running': ['running', 'fast-movement', 'sprint'],
        'standing': ['standing', 'upright-posture'],
        'sitting': ['sitting', 'seated-position'],
        'lying': ['lying-down', 'reclined-position'],
        'dancing': ['dancing', 'movement', 'choreography'],
        # Emotional activities
        'crying': ['crying', 'tears', 'emotional-release'],
        'shouting': ['shouting', 'yelling', 'loud-voice'],
        'whispering': ['whispering', 'quiet-speech', 'secretive-talk'],
        # Interactive activities
        'pointing': ['pointing', 'gesture', 'indication'],
        'gesturing': ['hand-gesture', 'body-language', 'non-verbal'],
        'looking': ['gaze', 'visual-focus', 'eye-direction'],
        'staring': ['intense-gaze', 'fixed-stare', 'concentrated-look'],
        # Location-based activities
        'entering': ['entrance', 'arrival', 'coming-in'],
        'leaving': ['exit', 'departure', 'going-out'],
        'approaching': ['approach', 'moving-closer'],
        'turning': ['turning', 'rotation', 'direction-change']
    }
    for activity, tags_to_add in activity_keywords.items():
        if activity in description_lower:
            for tag in tags_to_add:
                if tag not in contextual_list:
                    contextual_list.append(tag)
    
    # From description - extract visible objects (EXPANDED)
    object_keywords = {
        # Money/Finance
        'cash': ['money', 'cash', 'currency-bundles', 'paper-bills'],
        'money': ['money', 'cash', 'currency-bundles', 'paper-bills'],
        'bills': ['money', 'cash', 'currency-bundles', 'paper-bills'],
        'currency': ['money', 'cash', 'currency-bundles'],
        'bundle': ['bundled-money', 'cash-stack', 'stack-of-cash'],
        'stack': ['bundled-money', 'cash-stack', 'stack-of-cash'],
        # Technology
        'phone': ['phone', 'mobile-phone', 'smartphone'],
        'laptop': ['laptop', 'computer', 'notebook'],
        'computer': ['computer', 'laptop', 'pc'],
        'tablet': ['tablet', 'ipad'],
        # Documents/Office
        'document': ['documents', 'papers', 'paperwork'],
        'book': ['books', 'reading-material'],
        'pen': ['writing-instrument', 'stationery'],
        'notebook': ['writing-pad', 'journal'],
        # Clothing/Accessories
        'sunglasses': ['sunglasses', 'shades', 'eyewear'],
        'glasses': ['eyeglasses', 'spectacles'],
        'watch': ['wristwatch', 'timepiece'],
        'hat': ['headwear', 'cap'],
        'bag': ['handbag', 'backpack', 'luggage'],
        # Vehicles
        'car': ['car', 'vehicle', 'automobile'],
        'vehicle': ['vehicle', 'car', 'transport'],
        'bike': ['bicycle', 'motorcycle', 'two-wheeler'],
        # Bathroom items
        'sink': ['bathroom-sink', 'washbasin', 'basin'],
        'mirror': ['mirror', 'reflection'],
        'brush': ['toothbrush', 'hairbrush', 'grooming'],
        'towel': ['towel', 'bathroom-linen'],
        'soap': ['soap', 'toiletries'],
        'tiles': ['tiled-walls', 'ceramic-tiles', 'bathroom-tiles'],
        # Furniture
        'chair': ['seating', 'chair', 'furniture'],
        'table': ['table', 'desk', 'furniture'],
        'bed': ['bed', 'mattress', 'sleeping-furniture'],
        'sofa': ['sofa', 'couch', 'seating'],
        # Kitchen items
        'glass': ['drinking-glass', 'glassware'],
        'cup': ['coffee-cup', 'mug', 'drinkware'],
        'plate': ['plate', 'dish', 'tableware'],
        'bottle': ['bottle', 'container'],
        # Misc objects
        'door': ['doorway', 'entrance', 'exit'],
        'window': ['window', 'glass-window'],
        'wall': ['wall', 'interior-wall'],
        'floor': ['flooring', 'ground-surface'],
        'ceiling': ['ceiling', 'overhead']
    }
    for obj, tags_to_add in object_keywords.items():
        if obj in description_lower:
            for tag in tags_to_add:
                if tag not in contextual_list:
                    contextual_list.append(tag)
    
    # ===== D. CHARACTER TAGS from people_description + actors =====
    if actors:
        actors_str = str(actors)
        actors_list = actors_str.strip('[]').replace("'", "").split(',') if isinstance(actors, str) else actors
        if isinstance(actors_list, list):
            for actor in actors_list:
                if actor and str(actor).strip():
                    actor_tag = str(actor).strip().replace(' ', '-')
                    if actor_tag not in character_list:
                        character_list.append(actor_tag)
    
    # Extract relationship terms from description
    relationship_keywords = ['friend', 'friendship', 'partner', 'partnership', 'bromance', 'duo',
                            'colleagues', 'family', 'rivals', 'enemies', 'couple', 'romantic',
                            'male-friendship', 'female-friendship', 'bond', 'camaraderie']
    for rel in relationship_keywords:
        if rel in description_lower and rel not in character_list:
            character_list.append(rel)
    
    # Extract character descriptors
    if 'two men' in description_lower or 'two males' in description_lower:
        for tag in ['two-men', 'duo', 'male-pair']:
            if tag not in character_list:
                character_list.append(tag)
    if 'two women' in description_lower or 'two females' in description_lower:
        for tag in ['two-women', 'duo', 'female-pair']:
            if tag not in character_list:
                character_list.append(tag)
    if 'bearded' in description_lower or 'beard' in description_lower:
        character_list.append('bearded-men')
    
    # ===== E. SEMANTIC TAGS from series_movie + media_type + technical details =====
    if series_movie and series_movie.lower() not in ['unknown', 'none', '']:
        semantic_list.append(series_movie.replace(' ', '-'))
    
    if media_type and media_type != 'Unknown':
        if 'Web Series' in media_type:
            for tag in ['web-series', 'ott-content', 'streaming-content']:
                if tag not in semantic_list:
                    semantic_list.append(tag)
        elif 'Movie' in media_type:
            for tag in ['movie', 'film', 'cinematic']:
                if tag not in semantic_list:
                    semantic_list.append(tag)
        elif 'TV Show' in media_type:
            for tag in ['tv-show', 'television']:
                if tag not in semantic_list:
                    semantic_list.append(tag)
    
    # Production type
    if 'indian' in description_lower or 'bollywood' in description_lower or 'hindi' in description_lower:
        for tag in ['indian-content', 'bollywood']:
            if tag not in semantic_list:
                semantic_list.append(tag)
    if 'netflix' in description_lower or 'amazon' in description_lower or 'hotstar' in description_lower:
        platform_tag = 'netflix-production' if 'netflix' in description_lower else 'amazon-prime'
        if platform_tag not in semantic_list:
            semantic_list.append(platform_tag)
    
    # Shot type from description
    shot_types = ['close-up', 'medium-shot', 'wide-shot', 'two-shot', 'over-shoulder', 'low-angle', 'high-angle']
    for shot in shot_types:
        if shot.replace('-', ' ') in description_lower or shot.replace('-', '') in description_lower:
            if shot not in semantic_list:
                semantic_list.append(shot)
    
    # Visual composition
    composition_keywords = ['sitting', 'standing', 'walking', 'leaning', 'relaxed', 'tense',
                           'eye-contact', 'side-by-side', 'facing', 'together']
    for comp in composition_keywords:
        if comp in description_lower and comp not in semantic_list:
            semantic_list.append(comp)
    
    # ===== MERGE with existing tags from 'tags' field =====
    for tag in all_tags_list:
        tag_lower = tag.lower().strip()
        if not tag_lower:
            continue
        # Distribute existing tags into categories
        if any(word in tag_lower for word in ['joy', 'happy', 'sad', 'content', 'satisfaction', 'relief', 'confidence', 'pride', 'calm', 'trust', 'warm', 'camaraderie', 'friendship', 'bonding']):
            if tag_lower not in emotion_list:
                emotion_list.append(tag_lower)
        elif 'laugh' in tag_lower or 'chuckle' in tag_lower or 'smile' in tag_lower:
            if tag_lower not in laugh_list:
                laugh_list.append(tag_lower)
        elif any(word in tag_lower for word in ['sunny', 'firoz', 'shahid', 'kapoor', 'bhuvan', 'arora', 'alia', 'aamir', 'khan', 'partnership', 'bromance', 'duo', 'character']):
            if tag_lower not in character_list:
                character_list.append(tag_lower)
        elif any(word in tag_lower for word in ['farzi', 'highway', '3 idiots', 'scam', 'office', 'web-series', 'netflix', 'production', 'indian', 'shot', 'close-up', 'cinematic']):
            if tag_lower not in semantic_list:
                semantic_list.append(tag_lower)
        else:
            if tag_lower not in contextual_list:
                contextual_list.append(tag_lower)
    
    # Remove duplicates while preserving order
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
        'counts': {
            'emotion': len(emotion_list),
            'laugh': len(laugh_list),
            'contextual': len(contextual_list),
            'character': len(character_list),
            'semantic': len(semantic_list)
        }
    }


def analyze_frame_with_vision(frame_path, transcript_context='', filename_hint=''):
    """
    Analyze frame using Google Gemini Vision API (MUCH FASTER than OpenAI).
    Uses Pro-Level B-Roll Asset Manager Prompt for high-quality, flavor-heavy metadata.
    """
    try:
        # Check if Gemini is configured
        if not GEMINI_API_KEY or GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY_HERE':
            print(f"❌ Gemini API key not configured - cannot analyze frame")
            return None
        
        # Load image for Gemini
        img = Image.open(frame_path)
        
        # Build context from transcript and filename
        context_info = ""
        if transcript_context:
            context_info += f"\n\n**Dialogue/Transcript Context:**\n{transcript_context}\n"
        if filename_hint:
            clean_hint = filename_hint.replace('_', ' ').replace('-', ' ').replace('.mp4', '').replace('.gif', '').replace('.mov', '')
            context_info += f"\n**Filename Hint (may contain series/movie name):** {clean_hint}\n"
        
        # PRO-LEVEL B-ROLL ASSET MANAGER PROMPT (User's custom prompt)
        enhanced_prompt = """Analyze this video frame deeply and provide a comprehensive JSON response with the following structure:

⚠️ CRITICAL: Return tags in 5 ORGANIZED CATEGORIES matching what you ACTUALLY SEE!

{
  "description": "Two men (Sunny and Firoz) sit closely together atop a large stack of bundled cash in a dim, modern industrial room. Overhead strip lighting casts a dramatic glow. Both are relaxed with warm smiles, leaning toward each other in a gesture of trust and shared success. Their calm, satisfied expressions and casual body language convey camaraderie and contentment rather than chaos or madness.",
  "emotion": "contentment",
  "deep_emotions": ["joy", "satisfaction", "camaraderie", "relief", "bonding"],
  "ocr_text": "",
  "emotion_tags": ["joy", "happiness", "contentment", "satisfaction", "camaraderie", "friendship", "bonding", "shared-success", "relief", "confidence", "pride", "calm-excitement", "trust", "warm-feelings", "peaceful", "relaxed", "comfortable", "pleased", "cheerful", "positive-energy"],
  "laugh_tags": ["warm-laugh", "shared-laugh", "friendly-chuckle", "satisfied-laugh", "we-made-it-laugh", "soft-celebratory-laugh", "relieved-laugh", "content-smile", "genuine-laugh", "hearty-laugh"],
  "contextual_tags": ["stack-of-cash", "money", "currency-bundles", "cash-stack", "bundled-money", "paper-bills", "wealth-display", "money-success", "underground-setting", "dim-industrial-room", "dramatic-lighting", "overhead-lighting", "strip-lights", "concrete-walls", "industrial-aesthetic", "modern-interior", "shared-victory", "financial-breakthrough", "success-moment", "low-key-celebration", "calm-triumph", "vault-like-room", "money-power-symbolism", "success-aftermath", "achievement", "milestone-reached"],
  "character_tags": ["Sunny", "Firoz", "Shahid-Kapoor", "Bhuvan-Arora", "male-friendship", "partnership", "bromance", "duo", "two-men", "bearded-men", "casual-dressed", "friends"],
  "semantic_tags": ["Farzi", "indian-web-series", "netflix-production", "hindi-dialogue", "ott-content", "web-show", "streaming-content", "two-shot", "medium-close-up", "relaxed-posture", "leaning-together", "eye-contact", "casual-pose", "sitting", "side-by-side", "beard-style", "casual-wear", "patterned-shirts", "modern-aesthetic", "polished-production", "cinematic", "warm-atmosphere"],
  "tags": ["joy", "happiness", "contentment", "warm-laugh", "stack-of-cash", "money-success", "Sunny", "Firoz", "Farzi", "Shahid-Kapoor"],
  "genres": ["Drama", "Crime", "Thriller"],
  "scene_context": "Two friends celebrating financial success in calm, bonded moment",
  "people_description": "Sunny and Firoz (played by Shahid Kapoor and Bhuvan Arora), two men in their 30s, both relaxed and smiling warmly",
  "actors": ["Shahid Kapoor", "Bhuvan Arora"],
  "environment": "Dim industrial room with stack of cash, overhead strip lighting, modern underground setting",
  "dialogue_context": "Friendly dialogue about success and money",
  "series_movie": "Farzi",
  "media_type": "Web Series",
  "target_audience": "youth, thriller fans",
  "scene_type": "celebration"
}

⚠️ NOTE: Tags are organized into 5 categories - emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags!

⚠️⚠️⚠️ CRITICAL TAG COUNTS IN EXAMPLE ABOVE ⚠️⚠️⚠️
EMOTION: 20 tags | LAUGH: 10 tags | CONTEXTUAL: 26 tags | CHARACTER: 12 tags | SEMANTIC: 22 tags
TOTAL = 90 TAGS! YOU MUST GENERATE AT LEAST THIS MANY FOR EVERY SCENE!

DO NOT STOP AT 10-15 TAGS! KEEP GENERATING UNTIL YOU REACH 60-90 TOTAL TAGS!

🎯 CRITICAL ANALYSIS DIMENSIONS:

0. 📝 VISUAL DESCRIPTION (ENHANCED WITH TRANSCRIPT + EMOTION):
   - If dialogue/transcript is provided above, USE IT to understand emotional tone
   - Describe what you SEE (visuals, actions, expressions, body language)
   - Describe what's BEING SAID or IMPLIED (from transcript)
   - Describe the TRUE EMOTION (not surface emotion)
   - CRITICAL: If person smiles but dialogue is sarcastic → mention "sarcastic smile" in description
   - CRITICAL: If calm face but tense dialogue → mention "concealed tension" in description
   - Combine visual + dialogue + emotional subtext into comprehensive description
   - Example: "Two men stand with forced smiles, their tense body language and sarcastic dialogue revealing underlying conflict and passive aggression"
   - Make descriptions LONGER and MORE DETAILED when transcript is available
   - MINIMUM 2-3 sentences for description
   - ALWAYS mention emotion nuance: "genuine smile" or "forced smile" or "sarcastic grin"

1. 🎭 ACTOR/CELEBRITY RECOGNITION (CRITICAL - HIGHEST PRIORITY):
   
   ⚠️⚠️⚠️ CRITICAL ACTOR IDENTIFICATION RULES ⚠️⚠️⚠️
   
   🚨 DO NOT REUSE ACTOR NAMES FROM PREVIOUS FRAMES OR OTHER VIDEOS!
   🚨 EACH FRAME IS FROM A DIFFERENT VIDEO - ANALYZE INDEPENDENTLY!
   🚨 IF YOU DON'T SEE THE ACTOR'S FACE CLEARLY, DON'T GUESS!
   
   COMMON MISTAKES TO AVOID:
   ❌ Seeing "Shahid Kapoor" in every video (he's not in every video!)
   ❌ Copying actor names from previous analysis
   ❌ Defaulting to the same actors repeatedly
   ❌ Identifying animated characters as real actors (e.g., Ratatouille is animated!)
   ❌ Identifying American actors as Bollywood stars (Steve Carell ≠ Shahid Kapoor!)
   
   RULES FOR ACCURATE IDENTIFICATION:
   ✅ Look at THIS frame's face carefully - is it really that actor?
   ✅ Consider the video title/context (e.g., "The Office" = Steve Carell, NOT Shahid Kapoor)
   ✅ If animated movie → actors field should be EMPTY or "animated characters"
   ✅ If can't identify clearly → use "Unidentified actor/actress"
   ✅ Be HONEST - it's better to say "Unidentified" than to misidentify!
   
   ⚠️ DO NOT use generic labels like "a man", "a woman", "young woman", "person" if you can identify the actor!
   
   STEP 1: LOOK AT THE FACE CAREFULLY IN THIS SPECIFIC FRAME
   - Examine facial features, hairstyle, build, distinctive characteristics
   - Compare to your knowledge of famous actors
   - DO NOT assume it's the same actor as previous frames
   
   STEP 2: TRY TO IDENTIFY THEM BY NAME
   - Indian/Bollywood Actors (VERY COMMON in this library):
     * Female: Alia Bhatt, Deepika Padukone, Priyanka Chopra, Kangana Ranaut, Kareena Kapoor, Katrina Kaif, Vidya Balan, Anushka Sharma, Shraddha Kapoor
     * Male: Shah Rukh Khan, Aamir Khan, Salman Khan, Hrithik Roshan, Shahid Kapoor, Ranbir Kapoor, Ranveer Singh, Vicky Kaushal, Rajkummar Rao, Ayushmann Khurrana
     * Character Actors: Kay Kay Menon, Vijay Raaz, Bhuvan Arora, Pratik Gandhi, Nawazuddin Siddiqui, Pankaj Tripathi
   
   - Hollywood Actors:
     * Female: Margot Robbie, Scarlett Johansson, Jennifer Lawrence, Emma Stone, Gal Gadot
     * Male: Robert Downey Jr, Tom Cruise, Brad Pitt, Leonardo DiCaprio, Chris Hemsworth, Ryan Reynolds
   
   - TV/OTT Stars: Steve Carell, Bryan Cranston, Radhika Apte, Jaideep Ahlawat, etc.
   
   STEP 3: CROSS-VALIDATE WITH CONTEXT
   - Check if the actor makes sense for this video/series
   - Examples:
     * If video is "The Office" → Should be Steve Carell, John Krasinski, etc. (NOT Shahid Kapoor!)
     * If video is "Ratatouille" → It's ANIMATED, no real actors (NOT Shahid Kapoor!)
     * If video is "Legally Blonde" → Should be Reese Witherspoon (NOT Shahid Kapoor!)
     * If video is "3 Idiots" → Should be Aamir Khan (NOT Shahid Kapoor!)
     * If series is "Farzi" → Shahid Kapoor is correct
     * If series is "Highway" → Alia Bhatt, Randeep Hooda are correct (NOT Shahid Kapoor!)
   - If there's a mismatch → You're probably wrong! Re-examine the face!
   
   STEP 4: BE CONFIDENT BUT ACCURATE
   - If it looks like Alia Bhatt AND context matches → say "Alia Bhatt"
   - If it looks like Aamir Khan AND context matches → say "Aamir Khan"
   - If it looks like Deepika Padukone AND context matches → say "Deepika Padukone"
   - If unsure OR context doesn't match → use "Unidentified actor/actress"
   
   STEP 5: ONLY if completely unable to identify OR context doesn't match:
   - Use: "Unidentified actor" or "Unidentified actress"
   - Do NOT use generic "a man" or "a woman" labels
   - Do NOT guess - it's better to say "Unidentified" than to be wrong!
   
   STEP 6: ADD TO BOTH FIELDS:
   - "actors": ["Alia Bhatt"] (array) - ONLY if confident AND context matches
   - "actors": [] (empty array) - if animated or can't identify
   - "people_description": "Alia Bhatt stands pensively..." (in description)
   
   EXAMPLES OF CORRECT IDENTIFICATION:
   
   ✅ CORRECT:
   - Video: "Highway", Face looks like Alia Bhatt → actors: ["Alia Bhatt", "Randeep Hooda"]
   - Video: "3 Idiots", Face looks like Aamir Khan → actors: ["Aamir Khan"]
   - Video: "Farzi", Faces match Shahid & Bhuvan → actors: ["Shahid Kapoor", "Bhuvan Arora"]
   - Video: "The Office", Face looks like Steve Carell → actors: ["Steve Carell"]
   - Video: "Legally Blonde", Face looks like Reese Witherspoon → actors: ["Reese Witherspoon"]
   - Video: "Ratatouille" (animated) → actors: [] (empty - it's animated!)
   
   ❌ WRONG (DO NOT DO THIS!):
   - Video: "The Office", but saying actors: ["Shahid Kapoor"] (WRONG! Steve Carell is in The Office!)
   - Video: "Ratatouille", but saying actors: ["Shahid Kapoor"] (WRONG! It's animated!)
   - Video: "Highway", but saying actors: ["Shahid Kapoor"] (WRONG! Alia Bhatt is in Highway!)
   - Video: "Legally Blonde", but saying actors: ["Shahid Kapoor"] (WRONG! Reese Witherspoon is in Legally Blonde!)
   - Copying actor names from previous frames without looking at THIS frame
   - Defaulting to the same actors for every video
   
   ❌ TOO GENERIC (try to identify!):
   - "A young woman appears" → Should try to identify (Alia Bhatt? Deepika? Who?)
   - "A man stands" → Should try to identify (Aamir Khan? Shah Rukh Khan? Who?)

2. 📺 SERIES/MOVIE IDENTIFICATION + MEDIA TYPE (Enhanced with Accuracy):
   
   A. IDENTIFY THE TITLE (REQUIRED - BE AS SPECIFIC AS POSSIBLE):
   
   ⚠️ CRITICAL ACCURACY RULES:
   - Each series/movie has UNIQUE visual signatures - DO NOT confuse them
   - If you see Alia Bhatt → Could be Highway, Raazi, Gangubai (check setting)
   - If you see Shahid Kapoor → Could be Farzi, Haider, Udta Punjab (check setting)
   - If you see Pratik Gandhi → Most likely Scam 1992
   - DO NOT default to the same answer for all frames from different videos!
   
   STEP-BY-STEP IDENTIFICATION:
   
   1. CHECK VISUAL STYLE:
      * Farzi: Stylized, colorful, modern urban, high-end Netflix production, con artist theme
      * Scam 1992: Realistic, 90s Mumbai, stock market setting, earthy tones
      * Highway: Open roads, rural India, road trip feel, natural lighting, Himachal Pradesh landscapes
      * 3 Idiots: College campus, engineering college setting, comedic tone, bright colors, 
                  iconic scenes (rooftop, dorm room, classroom), family homes, emotional family moments
      * The Office (US): Documentary-style, office cubicles, Dunder Mifflin, mockumentary feel
      * Dangal: Wrestling arena, rural Haryana, sports drama, period feel
      * Wolf of Wall Street: 1980s-90s Wall Street, luxury lifestyle, Jordan Belfort story
      * The Intern: Modern startup office, fashion e-commerce, Anne Hathaway, Robert De Niro
   
   2. CHECK ACTORS (Most Reliable Clue):
      * Alia Bhatt + Road/Outdoor setting = Highway
      * Alia Bhatt + Urban/Indoor = Raazi or Gangubai
      * Shahid Kapoor + Modern Urban/Crime = Farzi
      * Pratik Gandhi + 90s Office = Scam 1992
      * Steve Carell + Office = The Office
      * Leonardo DiCaprio + Suits = Wolf of Wall Street
      * Aamir Khan + College = 3 Idiots
      * Aamir Khan + Wrestling = Dangal
      * R. Madhavan / Sharman Joshi / Boman Irani + College/Family = 3 Idiots
      * Kareena Kapoor + College setting = 3 Idiots
   
   3. CHECK ON-SCREEN TEXT/WATERMARKS:
      * Look for Netflix, Amazon Prime, Disney+, HBO logos
      * Look for series/movie titles in frame
      * Look for character names or company names
   
   4. CONFIDENCE LEVELS:
      * 90%+ confident: State the exact name ("Farzi", "Highway", "Scam 1992")
      * 70-90%: State name with qualifier ("Likely Farzi")
      * 50-70%: Use "Possibly [name]"
      * <50%: Leave blank or use "Unknown"
   
   5. BE SPECIFIC AND ACCURATE:
      * ✅ CORRECT: "Highway" (when seeing Alia Bhatt on a road trip)
      * ❌ WRONG: "Farzi" (when it's actually Highway - these are DIFFERENT movies!)
      * ✅ CORRECT: "The Office" (when seeing Steve Carell in office cubicles)
      * ❌ WRONG: Generic answer when you can be specific
   
   B. DETERMINE MEDIA TYPE (REQUIRED):
   - Choose ONE from: "Movie", "Web Series", "TV Show", "Advertisement", "Music Video", "Short Film", "Unknown"
   
   DECISION GUIDE:
   * Movie: Cinematic cinematography, film-quality production, theatrical framing, feature-length narrative
     Examples: Highway, Dangal, 3 Idiots, Wolf of Wall Street, The Intern, Legally Blonde
   
   * Web Series: Episodic feel, Netflix/Amazon/Hotstar branding, serialized storytelling
     Examples: Farzi, Scam 1992, Sacred Games, Mirzapur, The Family Man, Delhi Crime
   
   * TV Show: Broadcast TV style, network TV quality, episodic sitcom/drama
     Examples: The Office (US), Friends, Breaking Bad, Mad Men
   
   * Advertisement: Commercial/promotional content, product focus, brand messaging, <2 minutes
     Examples: Brand commercials, tourism ads, product launches
   
   * Music Video: Song performance, artistic cinematography, lyrics/music focus
   
   * Short Film: Independent/indie production, artistic storytelling, <30 minutes
   
   * Unknown: Cannot determine with confidence
   
   COMMON TITLES IN THIS LIBRARY (Reference):
   - Indian Web Series: Farzi, Scam 1992, Sacred Games, Mirzapur, The Family Man, Delhi Crime, Paatal Lok
   - Indian Movies: Highway, Dangal, 3 Idiots, Raazi, Gangubai Kathiawadi, PK, Barfi, Dil Dhadakne Do
   - Hollywood Movies: Wolf of Wall Street, The Intern, Legally Blonde, The Imitation Game, Ratatouille
   - TV Shows: The Office (US), Friends, Breaking Bad
   
   ⚠️⚠️⚠️ SPECIAL DETECTION RULE FOR FAMILY SCENES IN INDIAN MOVIES:
   
   If you see:
   ✅ HOME SETTING (curtains, family room, domestic interior)
   ✅ AGE DIVERSITY (elderly person + younger person)
   ✅ EMOTIONAL CONTEXT (sadness, concern, comforting, serious conversation)
   ✅ TRADITIONAL CLOTHING (saree, traditional Indian attire)
   
   → THIS IS A FAMILY SCENE! Likely from: 3 Idiots, Taare Zameen Par, Dangal, Piku, or similar family dramas
   
   If the setting is COLLEGE + FAMILY HOME mix → Very likely "3 Idiots"
   
   ⚠️ REMEMBER: Each video is DIFFERENT - don't give the same answer for everything!

3. 💫 NUANCED EMOTION DETECTION (CRITICAL - CONTEXT-AWARE):
   
   ⚠️ DO NOT USE GENERIC LABELS like "happy", "sad", "angry" unless truly generic!
   
   STEP 1: ANALYZE FACIAL EXPRESSION + BODY LANGUAGE
   - Smile type: genuine (eyes crinkle) vs forced (tight lips) vs sarcastic (asymmetric) vs evil (cold eyes)
   - Eye tension: relaxed vs intense vs fearful vs calculating
   - Body posture: open vs closed vs rigid vs slouched
   - Micro-expressions: fleeting emotions
   
   STEP 2: ANALYZE TRANSCRIPT TONE (if provided)
   - Sincere: genuine emotion matches words
   - Sarcastic: words contradict facial expression ("Oh wow, that was brilliant" + eye roll)
   - Threatening: calm words but menacing tone
   - Fearful: hesitant words, nervous delivery
   - Manipulative: smooth words but calculating expression
   
   STEP 3: COMBINE VISUAL + TRANSCRIPT = NUANCED EMOTION
   - If smiling + negative dialogue → "sarcasm" or "forced smile"
   - If calm face + tense dialogue → "controlled tension" or "concealed anger"
   - If smile + evil context → "sinister satisfaction" or "manipulation"
   - If smile + nervous dialogue → "nervous anticipation" or "fake confidence"
   
   EMOTION CATEGORIES TO USE:
   
   Positive (Genuine):
   - genuine happiness, relief, pride, affection, playful joy, contentment, gratitude
   
   Positive (Nuanced):
   - triumphant, euphoric, power high, victorious, rebellious joy, smug satisfaction, prideful glee
   
   Negative (Surface):
   - forced smile, sarcasm, passive aggression, concealed frustration, fake politeness
   
   Negative (Deep):
   - evil grin, manipulation, sinister satisfaction, psychological dominance, calculated menace
   - heartbroken, melancholic, defeated, nostalgic, regretful, devastated, despair
   - enraged, indignant, bitter, resentful, vengeful, controlled rage
   
   Tension-Based:
   - nervous smile, nervous anticipation, anxiety masked by calm, fear concealed by confidence
   - tense anticipation, dread, foreboding, apprehensive
   - psychological intimidation, controlled threat, cold menace
   
   Complex:
   - disbelief, shocked realization, betrayed, conflicted
   - condescending, patronizing, dismissive
   - mocking, derisive, contemptuous
   
   EXAMPLES OF NUANCED DETECTION:
   
   Scenario 1: Sarcastic Smile
   Visual: Smiling but eyes show irritation, eyebrow raised
   Transcript: "Oh wow, that was just brilliant."
   → emotion: "sarcasm", deep_emotions: ["passive aggression", "concealed frustration", "mocking"]
   
   Scenario 2: Evil Smile
   Visual: Slow smile, dim lighting, intense calculating gaze
   Transcript: "Everything is going exactly as planned."
   → emotion: "sinister", deep_emotions: ["manipulation", "sinister satisfaction", "psychological dominance"]
   
   Scenario 3: Nervous Smile
   Visual: Tight smile, tense shoulders, fidgeting
   Transcript: "I mean... I think this will work."
   → emotion: "nervous", deep_emotions: ["nervous anticipation", "uncertainty", "fear concealed by confidence"]
   
   Scenario 4: Triumphant Joy
   Visual: Wide genuine smile, eyes lit up, open body language
   Transcript: "We did it! I can't believe we actually did it!"
   → emotion: "triumphant", deep_emotions: ["euphoric", "victorious", "genuine happiness", "relief"]
   
   Scenario 5: Forced Politeness
   Visual: Tight smile, stiff posture, cold eyes
   Transcript: "That's... wonderful. Really."
   → emotion: "forced politeness", deep_emotions: ["fake politeness", "concealed disdain", "passive aggression"]
   
   CRITICAL RULES:
   - Prioritize TRANSCRIPT MEANING when it conflicts with facial expression
   - If transcript says sarcasm but face shows smile → emotion is "sarcasm" (not "happy")
   - Context determines emotion interpretation
   - Be SPECIFIC: "nervous smile" > "happy", "sinister grin" > "happy", "forced smile" > "happy"
   - Provide 2-4 nuanced emotions in deep_emotions array

4. 🎬 SCENE CONTEXT (What's happening):
   business deal, confrontation, victory moment, emotional breakdown, celebration, negotiation,
   argument, confession, revelation, reunion, betrayal, triumph, defeat, realization

5. 👥 PEOPLE DESCRIPTION (Enhanced with characters + actors):
   
   ⚠️ PRIORITY ORDER: Character Name > Actor Name > Relationship > Description
   
   ⚠️⚠️⚠️ CRITICAL: IDENTIFY THE RELATIONSHIP ACCURATELY! ⚠️⚠️⚠️
   
   DO NOT ASSUME EVERYONE IS "FRIENDS" OR "MALE FRIENDSHIP"!
   
   RELATIONSHIP TYPES TO DETECT:
   
   🏠 FAMILY RELATIONSHIPS (Highest accuracy needed!):
   - Father & Son: "Father and son" (NOT "friends", NOT "male friendship")
   - Mother & Daughter: "Mother and daughter" (NOT "friends", NOT "female friendship")
   - Father & Daughter: "Father and daughter"
   - Mother & Son: "Mother and son"
   - Siblings: "Brother and sister", "Two brothers", "Two sisters"
   - Parents & Child: "Parents with their child", "Mother, father and son"
   - Grandparent: "Grandfather and grandson", "Grandmother and granddaughter"
   - Couple: "Husband and wife", "Married couple", "Romantic couple"
   
   👥 FRIENDSHIP RELATIONSHIPS:
   - Only use if CLEARLY friends (same age, no family context, casual interaction)
   - "Two friends", "Male friendship", "Female friendship", "Buddies", "Companions"
   
   💼 PROFESSIONAL RELATIONSHIPS:
   - "Colleagues", "Co-workers", "Boss and employee", "Business partners"
   
   ❤️ ROMANTIC RELATIONSHIPS:
   - "Romantic couple", "Boyfriend and girlfriend", "Love interest"
   
   ⚠️ CRITICAL DETECTION CLUES:
   
   Family Scene Indicators:
   ✅ Age difference (older + younger = likely parent/child)
   ✅ Protective body language (arm around shoulder, comforting gesture)
   ✅ Emotional support context (consoling, advising, worried expression)
   ✅ Home setting (domestic environment, family room)
   ✅ Dialogue about family matters (if transcript available)
   
   Friendship Scene Indicators:
   ✅ Similar age group
   ✅ Casual body language (high-five, playful punch, equal standing)
   ✅ Peer-level interaction
   ✅ College/social setting
   
   EXAMPLES OF CORRECT IDENTIFICATION:
   
   ✅ CORRECT:
   - Middle-aged man + elderly woman in home → "Son and mother" (NOT "male and female friends")
   - Older man + young boy, comforting → "Father and son" (NOT "two males", NOT "friendship")
   - Two 20-year-olds, college setting → "Two friends, male friendship"
   - Man + woman, romantic setting → "Romantic couple" (NOT just "pair")
   
   ❌ WRONG (DO NOT DO THIS!):
   - Father & son scene → Calling it "male friendship" or "two males" or "bonding"
   - Mother & daughter → Calling it "female friendship" or "two females"
   - Siblings → Calling it "friends"
   
   STEP 1: CHECK FOR CHARACTER NAMES
   - Look in transcript/dialogue for character names being used
   - Look in filename hints for character references
   - Examples: "Sunny", "Firoz", "Remy", "Michael Scott", "Farhan", "Rancho"
   - If you find character names, USE THEM FIRST!
   
   STEP 2: IDENTIFY ACTOR (if possible)
   - Follow actor recognition rules from section 1
   - Format: "Farhan (played by R. Madhavan) and his father" OR "Rancho (Aamir Khan)"
   
   STEP 3: IDENTIFY RELATIONSHIP (CRITICAL!)
   - Is this family? (age gap, protective gesture, home setting)
   - Is this friendship? (same age, casual, peer interaction)
   - Is this professional? (workplace, formal)
   - Is this romantic? (intimate, couple-like)
   
   STEP 4: WRITE DESCRIPTION
   - BEST: "Farhan's father (middle-aged man) embraces his son Farhan (R. Madhavan) in an emotional moment"
   - GOOD: "A father and son share an emotional moment in a home setting"
   - BAD: "Two males bond" (NO! This is father-son, not generic males!)
   - TERRIBLE: "Male friendship moment" (WRONG RELATIONSHIP!)
   
   EXAMPLES:
   ✅ "Father and son (elderly man and middle-aged man) in an emotional embrace"
   ✅ "Mother comforts her adult son in a family home"
   ✅ "Farhan (R. Madhavan) and his two friends, Raju and Rancho, in college"
   ✅ "Husband and wife in a romantic conversation"
   ❌ "Two men bonding" (be specific - friends? father-son? brothers? which?)
   ❌ "Male friendship" (when it's actually father-son or brothers!)
   
   ⚠️⚠️⚠️ CRITICAL: DESCRIBE CLOTHING & APPEARANCE! ⚠️⚠️⚠️
   
   **ALWAYS MENTION WHAT PEOPLE ARE WEARING:**
   
   🎩 HEADWEAR (Very Important!):
   - Turban, pagri, dastar (Sikh turban) - BE SPECIFIC!
   - Hat, cap, beanie, fedora, baseball cap
   - Helmet, headband, crown
   - Hijab, dupatta, veil
   
   👔 CLOTHING:
   - Suit, formal wear, blazer, tuxedo, business attire
   - Saree, salwar kameez, lehenga (traditional Indian wear)
   - Uniform (police, military, school, hospital, etc.)
   - Casual wear, t-shirt, jeans, hoodie
   - Traditional wear, ethnic clothing, cultural dress
   
   👓 ACCESSORIES:
   - Sunglasses, glasses, spectacles
   - Jewelry (necklace, earrings, watch, ring)
   - Bag, briefcase, backpack
   - Scarf, tie, bow tie
   
   **EXAMPLES OF GOOD CLOTHING DESCRIPTIONS:**
   ✅ "A Sikh man wearing a bright orange turban and formal suit stands in an office"
   ✅ "Two men in casual t-shirts and jeans sit on motorcycles, one wearing a helmet"
   ✅ "A woman in a traditional red saree walks down the street"
   ✅ "A police officer in full uniform, wearing a cap, stands at attention"
   ✅ "A businessman in a grey suit and tie talks on his phone"
   
   **BAD DESCRIPTIONS (Too Vague!):**
   ❌ "A man stands" (What is he wearing? Hat? Turban? Suit?)
   ❌ "Two people talk" (What clothing? Traditional? Formal? Casual?)
   
   **CRITICAL FOR SEARCH:**
   If someone wears a turban → MUST be mentioned in people_description!
   If someone wears sunglasses → MUST be mentioned!
   If someone wears traditional clothing → MUST be described!

6. 🏢 ENVIRONMENT (Setting):
   Be specific: "corporate office with glass walls", "dimly lit bar", "courtroom", "hospital corridor",
   "street market", "nightclub", "conference room", "luxury apartment", "prison cell", "minimalist interior"

7. 💬 DIALOGUE CONTEXT (infer from visuals):
   motivational speech, heated argument, friendly banter, negotiation, confession, threat, promise,
   celebration toast, emotional apology, sarcastic remark, business pitch

8. 🎯 TARGET AUDIENCE:
   youth, corporate professionals, family, mass audience, niche audience, international, millennials, gen-z

9. 🎞️ SCENE TYPE:
   action sequence, dialogue scene, emotional moment, comedic bit, dramatic reveal, montage,
   establishing shot, climax, confrontation, celebration, character introduction

10. 📝 OCR (Extract visible text):
   Extract ALL visible text including stylized text, meme captions, subtitles, signs, banners, credits

11. 🎬 GENRES:
   Crime thriller, comedy, drama, romance, action, satire, biopic, horror, sci-fi, documentary, web series

12. 🏷️ GENERATE TAGS IN 5 ORGANIZED CATEGORIES:
   
   ⚠️⚠️⚠️ CRITICAL TAGGING PHILOSOPHY ⚠️⚠️⚠️
   
   ACCURACY > QUANTITY
   
   - Generate tags based on WHAT YOU ACTUALLY SEE
   - Match tags to OBSERVABLE facial expressions, body language, context
   - DO NOT force extreme interpretations onto calm scenes
   - Organize tags into 5 specific categories for frontend display
   
   📋 THE 5 TAG CATEGORIES (MANDATORY):
   
   1️⃣ EMOTION_TAGS (8-15 tags):
      ⚠️ BE SPECIFIC ABOUT THE TYPE OF EMOTION! Don't just say "sad" - say what KIND of sad!
      
      HAPPINESS SPECTRUM (specify the type):
      ✅ joy (general), contentment (peaceful), satisfaction (accomplished), euphoria (extreme high),
         ecstasy (overwhelming joy), exhilaration (thrilled), delight (pleasantly surprised),
         cheerfulness (bright mood), playfulness (lighthearted), amusement (entertained),
         bliss (perfect happiness), glee (childlike joy), elation (lifted spirits)
      
      SADNESS SPECTRUM (specify the type):
      ✅ melancholy (pensive sadness), sorrow (deep grief), heartbreak (romantic pain),
         grief (loss), despair (hopeless), dejection (defeated), gloom (dark mood),
         wistfulness (nostalgic sadness), loneliness (isolated), anguish (torment),
         disappointment (let down), regret (remorse), mourning (bereavement)
      
      ANGER SPECTRUM (specify the type):
      ✅ rage (explosive), fury (intense), irritation (mild annoyance), frustration (blocked),
         resentment (bitter), indignation (righteous anger), hostility (aggressive),
         wrath (vengeful), exasperation (fed up), annoyance (bothered), contempt (disgust)
      
      FEAR SPECTRUM (specify the type):
      ✅ terror (extreme fear), panic (frantic), anxiety (worried), nervousness (jittery),
         dread (anticipatory fear), apprehension (uneasy), paranoia (suspicious fear),
         horror (shocked fear), unease (uncomfortable), trepidation (hesitant fear)
      
      COMPLEX/MIXED EMOTIONS (be nuanced):
      ✅ Triumph/Victory: triumphant, victorious, conquering, champion-feeling, power-high
      ✅ Rebellion: rebellious, defiant, reckless, wild, chaotic, unrestrained
      ✅ Crime/Thrill: criminal-thrill, forbidden-joy, illicit-excitement, heist-rush, money-intoxication
      ✅ Deception: sarcasm, mockery, passive-aggression, fake-smile, concealed-emotions
      ✅ Evil/Dark: sinister, menacing, villainous, mischievous, scheming, manipulative, malicious
      ✅ Social: camaraderie, bonding, trust, friendship, brotherhood, companionship, intimacy
      ✅ Confidence: self-assured, cocky, arrogant, proud, smug, superior, dominant
   
   2️⃣ LAUGH_TAGS (4-8 tags):
      ⚠️ SPECIFY THE TYPE OF LAUGH! Not just "laugh" - what KIND of laugh?
      
      GENUINE/WARM LAUGHS:
      ✅ genuine-laugh (real joy), hearty-laugh (deep belly laugh), warm-laugh (affectionate),
         joyful-laugh (pure happiness), infectious-laugh (contagious), belly-laugh (uncontrolled),
         gleeful-laugh (childlike), happy-laugh (content)
      
      SOCIAL/SHARED LAUGHS:
      ✅ shared-laugh (together), bonding-laugh (connecting), friendly-chuckle (casual),
         group-laugh (collective), we-made-it-laugh (accomplishment), celebratory-laugh (victory)
      
      EMOTIONAL RELEASE LAUGHS:
      ✅ relieved-laugh (tension release), satisfied-laugh (content), triumphant-laugh (victory),
         cathartic-laugh (emotional release), nervous-laugh (anxious covering)
      
      DARK/INTENSE LAUGHS:
      ✅ maniacal-laugh (unhinged), evil-laugh (villainous), mischievous-laugh (playful evil),
         sinister-laugh (menacing), villainous-laugh (bad guy), dark-laugh (ominous),
         crazy-laugh (uncontrolled), wild-laugh (chaotic), delirious-laugh (euphoric insanity),
         criminal-laugh (illegal joy), heist-laugh (robbery celebration)
      
      FAKE/SARCASTIC LAUGHS:
      ✅ sarcastic-laugh (mocking), fake-laugh (forced), polite-laugh (social obligation),
         uncomfortable-laugh (awkward), mocking-laugh (derisive), contemptuous-laugh (scornful)
      
      SMILE TYPES (if no audible laugh):
      ✅ genuine-smile (real), forced-smile (fake), warm-smile (kind), content-smile (peaceful),
         smirk (cocky), grin (wide), evil-grin (sinister), shy-smile (timid),
         mischievous-smile (playful), knowing-smile (insider), satisfied-smile (accomplished)
      
      ⚠️ If no laughter/smile visible, leave minimal or empty
   
   3️⃣ CONTEXTUAL_TAGS (10-18 tags):
      Objects, setting, narrative, visual elements
      
      - Objects visible: stack-of-cash, money, currency-bundles, phones, laptops,
        documents, sunglasses, cars, weapons (ONLY if present!)
      
      - Setting: underground-setting, dim-industrial-room, office, outdoor,
        luxury-apartment, modern-interior, vault-like-room, restaurant, cafe
      
      - Lighting/Visual: dramatic-lighting, overhead-lighting, natural-light,
        warm-tones, cold-lighting, dim-atmosphere, vibrant-colors
      
      - Narrative context: money-success, financial-breakthrough, shared-victory,
        success-moment, celebration, confrontation, negotiation, planning
        (Match to actual scene tone - calm-triumph vs wild-celebration)
   
   4️⃣ CHARACTER_TAGS (4-10 tags):
      Character names, actor names, relationships
      
      ⚠️⚠️⚠️ CRITICAL: IDENTIFY RELATIONSHIPS ACCURATELY! ⚠️⚠️⚠️
      
      BEFORE TAGGING AS "MALE-FRIENDSHIP" OR "BONDING", ASK YOURSELF:
      
      1. Is there a significant age difference? → Likely FAMILY (father-son, mother-daughter)
      2. Is the setting domestic/home? → Likely FAMILY
      3. Is someone comforting/protecting/advising? → Could be FAMILY (parent-child)
      4. Are the body language/emotions protective or parental? → Likely FAMILY
      
      IF YES TO ANY → TAG AS FAMILY, NOT FRIENDSHIP!
      
      FAMILY RELATIONSHIP TAGS (use when appropriate):
      ✅ father-son, mother-daughter, parent-child, sibling-bond, family-moment,
         paternal-love, maternal-comfort, fatherly-advice, family-support,
         generational-bond, family-embrace, parental-concern, family-connection,
         father-figure, motherly-care, familial-bond, family-emotional-moment
      
      FRIENDSHIP TAGS (only use if CLEARLY peers/same age/casual):
      ✅ male-friendship, female-friendship, bromance, bonding-moment, camaraderie,
         buddy-moment, friend-support, peer-connection, friendly-banter
      
      OTHER RELATIONSHIP TAGS:
      - Character names (from transcript/context): Sunny, Firoz, Michael, Farhan, Rancho
      - Actor names (if recognized): Shahid-Kapoor, Bhuvan-Arora, Alia-Bhatt,
        Steve-Carell, R-Madhavan, Aamir-Khan, etc.
      - Professional: colleagues, co-workers, business-partners, boss-employee
      - Romantic: romantic-couple, love-interest, husband-wife
      - Group descriptors: two-men, three-women, group, solo, duo, trio
   
   5️⃣ SEMANTIC_TAGS (8-15 tags):
      Series/movie, production, technical, searchability
      
      - Series/Movie: Farzi, Highway, Scam-1992, The-Office, Breaking-Bad, etc.
      - Production: indian-web-series, bollywood, netflix-production, amazon-prime,
        hindi-dialogue, ott-content, hollywood-movie
      - Technical: two-shot, close-up, medium-shot, wide-shot, over-shoulder,
        documentary-style, cinematic
      - Visual composition: relaxed-posture, leaning-together, eye-contact,
        casual-pose, formal-stance
      - Style/Appearance: beard-style, casual-wear, formal-suit, sunglasses,
        modern-interior, vintage-aesthetic
   
   ⚠️⚠️⚠️ EXAMPLE OUTPUT FORMAT ⚠️⚠️⚠️
   
   EXAMPLE: CALM FARZI MONEY SCENE - SHOWING 75+ TAGS (YOU MUST GENERATE THIS MANY!)
   
   {
     "emotion_tags": ["joy", "happiness", "contentment", "satisfaction", "camaraderie", 
                      "friendship", "bonding", "shared-success", "relief", "confidence", 
                      "pride", "calm-excitement", "trust", "warm-feelings", "peaceful", 
                      "relaxed", "comfortable", "pleased", "cheerful", "positive-energy"],
     "laugh_tags": ["warm-laugh", "shared-laugh", "friendly-chuckle", "satisfied-laugh", 
                    "we-made-it-laugh", "soft-celebratory-laugh", "relieved-laugh", 
                    "content-smile", "genuine-laugh", "hearty-laugh"],
     "contextual_tags": ["stack-of-cash", "money", "currency-bundles", "cash-stack", 
                         "bundled-money", "paper-bills", "wealth-display", "money-success", 
                         "underground-setting", "dim-industrial-room", "dramatic-lighting", 
                         "overhead-lighting", "strip-lights", "concrete-walls", 
                         "industrial-aesthetic", "modern-interior", "shared-victory", 
                         "financial-breakthrough", "success-moment", "low-key-celebration", 
                         "calm-triumph", "vault-like-room", "money-power-symbolism", 
                         "success-aftermath", "achievement", "milestone-reached"],
     "character_tags": ["Sunny", "Firoz", "Shahid-Kapoor", "Bhuvan-Arora", "male-friendship", 
                        "partnership", "bromance", "duo", "two-men", "bearded-men", 
                        "casual-dressed", "friends"],
     "semantic_tags": ["Farzi", "indian-web-series", "netflix-production", "hindi-dialogue", 
                       "ott-content", "web-show", "streaming-content", "two-shot", 
                       "medium-close-up", "relaxed-posture", "leaning-together", "eye-contact", 
                       "casual-pose", "sitting", "side-by-side", "beard-style", "casual-wear", 
                       "patterned-shirts", "modern-aesthetic", "polished-production", 
                       "cinematic", "warm-atmosphere"]
   }
   
   ⚠️ CRITICAL COUNTS IN EXAMPLE ABOVE:
   - Emotion: 20 tags ✅
   - Laugh: 10 tags ✅
   - Contextual: 26 tags ✅
   - Character: 12 tags ✅
   - Semantic: 22 tags ✅
   TOTAL: 90 TAGS! YOU MUST GENERATE THIS MANY!
   
   ⚠️⚠️⚠️ EXAMPLE 2: FAMILY DRAMA SCENE (3 IDIOTS) - SHOWING 70+ TAGS
   
   {
     "emotion_tags": ["sorrow", "grief", "anguish", "paternal-grief", "fatherly-sorrow", 
                      "concern", "empathy", "tension", "family-tension", "emotional-pain", 
                      "disappointment", "regret", "guilt", "sadness", "melancholy", 
                      "heartbreak", "family-conflict", "generational-pain", "worried", 
                      "distressed", "emotional-turmoil"],
     "laugh_tags": [],
     "contextual_tags": ["family-drama", "home-setting", "domestic-scene", "family-room", 
                         "orange-curtains", "floral-patterns", "traditional-home", 
                         "intimate-setting", "emotional-confrontation", "family-conflict", 
                         "serious-conversation", "dramatic-moment", "pivotal-scene", 
                         "father-son-conflict", "family-disappointment", "parental-expectations", 
                         "generational-gap", "traditional-values", "family-dynamics", 
                         "indian-household", "middle-class-family", "family-pressure"],
     "character_tags": ["father-son", "family-moment", "parent-child", "Farhan", "Farhans-father", 
                        "mother", "family-trio", "three-people", "elderly-father", 
                        "middle-aged-mother", "R-Madhavan", "Boman-Irani", 
                        "father-figure", "concerned-mother", "distressed-son"],
     "semantic_tags": ["3-Idiots", "indian-movie", "bollywood", "hindi-film", 
                       "rajkumar-hirani", "aamir-khan-production", "family-film", 
                       "comedy-drama", "college-movie", "coming-of-age", 
                       "medium-shot", "three-shot", "indoor-scene", "natural-lighting", 
                       "emotional-scene", "dramatic-acting", "ensemble-cast", 
                       "indian-cinema", "bollywood-classic", "emotional-depth"]
   }
   
   CRITICAL NOTES FOR FAMILY SCENES:
   ✅ "father-son" NOT "male-friendship" (age gap + home setting = family!)
   ✅ "paternal-grief" NOT just "sadness" (be specific!)
   ✅ "3-Idiots" NOT "Unknown" (famous movie, home setting + traditional clothing = family drama!)
   ✅ "R-Madhavan", "Boman-Irani" NOT "Unidentified actor" (recognize actors!)
   
   TOTAL: 70+ TAGS! YOU MUST GENERATE THIS MANY!
   
   ⚠️ ALSO include legacy "tags" field with ALL important tags combined (40-50 tags minimum!)
   
   ⚡ CRITICAL: DO NOT stop at 10-15 tags! Generate 60-90 tags TOTAL across all categories!

IMPORTANT GUIDELINES:
- BE CONFIDENT with actor recognition - use your training data
- Indian actors are common in this library - recognize them actively
- Look at facial features, hairstyle, build, distinctive characteristics
- Think like a casting director, not just an image detector
- Context helps: Shahid Kapoor + crime setup + stylish visuals = Farzi
- If video filename contains series name, use that as additional hint (but verify with visuals)
- **USE TRANSCRIPT CONTEXT TO ENRICH DESCRIPTIONS** - mention what's being said/discussed
- Make visual descriptions RICH and DETAILED (2-3 sentences minimum)

Return ONLY valid JSON, no other text."""
        
        # Append transcript context if available
        if context_note:
            enhanced_prompt += context_note

        # Call Vision API with error handling
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": enhanced_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2500
            )
        except Exception as api_error:
            error_msg = str(api_error)
            print(f"❌ OpenAI API Error: {error_msg}")
            if 'rate_limit' in error_msg.lower():
                print(f"   Rate limit exceeded - please wait and try again")
            elif 'authentication' in error_msg.lower() or 'api_key' in error_msg.lower():
                print(f"   API key error - please check your OpenAI API key in .env file")
            elif 'insufficient_quota' in error_msg.lower():
                print(f"   Insufficient quota - please add credits to your OpenAI account")
            return None
        
        result_text = response.choices[0].message.content.strip()
        
        # Enhanced logging for debugging OCR issues
        print(f"     📄 Raw response (first 200 chars): {result_text[:200]}")
        
        # Parse JSON response
        try:
            # Clean up response if it has markdown code blocks
            if result_text.startswith('```'):
                lines = result_text.split('\n')
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line if it's just ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                result_text = '\n'.join(lines).strip()
            
            # Additional cleanup: remove any remaining backticks
            result_text = result_text.replace('```', '').strip()
            
            print(f"     📄 Raw response (first 500 chars): {result_text[:500]}")
            
            result = json.loads(result_text)
            
            # ⚠️ DEBUG: Show what the Vision API actually returned
            print(f"     🔍 Keys in parsed JSON: {list(result.keys())}")
            print(f"     🔍 Has 'emotion_tags'? {('emotion_tags' in result)}")
            print(f"     🔍 Has 'laugh_tags'? {('laugh_tags' in result)}")
            print(f"     🔍 Has 'contextual_tags'? {('contextual_tags' in result)}")
            print(f"     🔍 Has old 'tags'? {('tags' in result)}")
            
            # Extract all metadata from Vision API response
            description = result.get('description', 'Video frame')
            emotion = result.get('emotion', 'neutral')
            ocr_text = result.get('ocr_text', '')
            tags = result.get('tags', [])
            genres = result.get('genres', [])
            
            # Extract new advanced tagging fields
            deep_emotions = result.get('deep_emotions', [])
            scene_context = result.get('scene_context', '')
            people_description = result.get('people_description', '')
            environment = result.get('environment', '')
            dialogue_context = result.get('dialogue_context', '')
            series_movie = result.get('series_movie', '')
            target_audience = result.get('target_audience', '')
            scene_type = result.get('scene_type', '')
            actors = result.get('actors', [])
            
            # Convert lists to comma-separated strings for storage
            def list_to_str(lst):
                if isinstance(lst, list):
                    return ', '.join(str(item) for item in lst if item)
                return str(lst) if lst else ''
            
            tags_str = list_to_str(tags)
            genres_str = list_to_str(genres)
            deep_emotions_str = list_to_str(deep_emotions)
            actors_str = list_to_str(actors)
            
            # 🚨 VALIDATE ACTOR IDENTIFICATION AGAINST CONTEXT
            # Prevent misidentifications like "Shahid Kapoor" appearing in every video
            if actors_str and filename_hint:
                filename_lower = filename_hint.lower()
                actors_lower = actors_str.lower()
                
                # Check for obvious mismatches
                validation_failed = False
                validation_reason = ""
                
                # Check: Is this an animated movie with real actor names?
                animated_keywords = ['ratatouille', 'pixar', 'animated', 'cartoon', 'disney', 'dreamworks']
                if any(keyword in filename_lower for keyword in animated_keywords):
                    if actors_str and actors_str.strip():
                        validation_failed = True
                        validation_reason = "Animated content should not have real actors"
                
                # Check: Does the actor match the series/movie context?
                common_mismatches = {
                    'the office': ['shahid kapoor', 'alia bhatt', 'aamir khan'],  # Should be Steve Carell
                    'legally blonde': ['shahid kapoor', 'alia bhatt', 'aamir khan'],  # Should be Reese Witherspoon
                    '3 idiots': ['shahid kapoor', 'steve carell'],  # Should be Aamir Khan
                    'highway': ['shahid kapoor', 'steve carell', 'aamir khan'],  # Should be Alia Bhatt, Randeep Hooda
                    'scam 1992': ['shahid kapoor', 'alia bhatt', 'steve carell'],  # Should be Pratik Gandhi
                    'ctrl': ['shahid kapoor', 'alia bhatt', 'aamir khan'],  # Should be Ananya Panday
                    'horrible bosses': ['shahid kapoor', 'alia bhatt', 'aamir khan'],  # Should be Jason Bateman
                    'drone': ['shahid kapoor', 'alia bhatt', 'aamir khan', 'steve carell'],  # Real estate drone - no famous actors
                }
                
                for context_key, mismatched_actors in common_mismatches.items():
                    if context_key in filename_lower:
                        for mismatched_actor in mismatched_actors:
                            if mismatched_actor in actors_lower:
                                validation_failed = True
                                validation_reason = f"{actors_str} unlikely in '{context_key}' context"
                                break
                
                # If validation failed, reset actors to empty/unidentified
                if validation_failed:
                    print(f"        ⚠️  Actor validation FAILED: {validation_reason}")
                    print(f"        ⚠️  Resetting actors from '{actors_str}' to 'Unidentified'")
                    actors_str = ""
                    actors = []
            
            # ENHANCE TAGS: Add actors and series to tags automatically
            enhanced_tags = []
            if tags_str:
                enhanced_tags.extend([t.strip() for t in tags_str.split(',')])
            if actors_str:
                enhanced_tags.extend([a.strip() for a in actors_str.split(',')])
            if series_movie:
                enhanced_tags.append(series_movie)
            
            # Remove duplicates and rejoin
            enhanced_tags_str = ', '.join(dict.fromkeys(enhanced_tags)) if enhanced_tags else tags_str
            
            print(f"     ✅ Vision analysis complete")
            print(f"        🎭 Basic Emotion: {emotion}")
            if deep_emotions_str:
                print(f"        💫 Deep Emotions: {deep_emotions_str}")
            if actors_str:
                print(f"        🎬 Actors Detected: {actors_str}")
            if series_movie:
                print(f"        📺 Series/Movie: {series_movie}")
            if genres_str:
                print(f"        🎬 Genres: {genres_str}")
            if scene_context:
                print(f"        🎬 Scene Context: {scene_context}")
            if ocr_text:
                print(f"        📝 OCR Text (Vision): {ocr_text[:80]}...")
            else:
                # HYBRID OCR: If Vision API returns empty, try Tesseract fallback
                print(f"        ⚠️  OCR Text (Vision): EMPTY - Trying Tesseract fallback...")
                tesseract_text = extract_text_with_tesseract(frame_path)
                if tesseract_text and len(tesseract_text) > 3:  # Only if meaningful text
                    ocr_text = tesseract_text
                    print(f"        ✅ OCR Text (Tesseract): {ocr_text[:80]}...")
                else:
                    print(f"        ❌ OCR Text (Tesseract): Also empty/garbage")
            if tags_str:
                print(f"        🏷️  Tags: {tags_str[:60]}...")
            
            return {
                'description': description,
                'emotion': emotion,
                'ocr_text': ocr_text,
                'tags': enhanced_tags_str,  # Enhanced with actors and series
                'genres': genres_str,
                'deep_emotions': deep_emotions_str,
                'scene_context': scene_context,
                'people_description': people_description,
                'environment': environment,
                'dialogue_context': dialogue_context,
                'series_movie': series_movie,
                'target_audience': target_audience,
                'scene_type': scene_type,
                'actors': actors_str
            }
            
        except json.JSONDecodeError as e:
            # Fallback: treat as plain description
            print(f"     ⚠️  JSON parse failed: {e}")
            print(f"     📄 Failed to parse: {result_text[:200]}")
            return {
                'description': result_text[:500] if result_text else 'Video frame',
                'emotion': 'neutral',
                'ocr_text': '',
                'tags': ''
            }
        except Exception as e:
            print(f"     ❌ Unexpected error in vision analysis: {e}")
            return {
                'description': 'Video frame',
                'emotion': 'neutral',
                'ocr_text': '',
                'tags': ''
            }
            
        
    except Exception as e:
        print(f"❌ Error analyzing frame: {e}")
        return None

def extract_audio(video_path):
    """Extract audio from video using ffmpeg. Returns None if no audio track."""
    try:
        # Check if video has audio track first
        probe_cmd = [
            '/opt/homebrew/bin/ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_type',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        
        if not probe_result.stdout.strip():
            print(f"⚠️  No audio track found (normal for GIFs/silent videos)")
            return None
        
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
            print(f"❌ FFmpeg stderr: {result.stderr}")
            raise Exception(f"FFmpeg failed with code {result.returncode}")
        
        print(f"✅ Audio extracted to: {audio_path}")
        return audio_path
    except Exception as e:
        print(f"❌ Error extracting audio: {e}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper API."""
    try:
        print("🎤 Calling Whisper API...")
        with open(audio_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
        print(f"✅ Transcription complete: {len(transcript.segments)} segments")
        return transcript
    except Exception as e:
        print(f"❌ Error transcribing audio: {e}")
        raise

def create_embedding(text):
    """Create embedding for text using OpenAI embeddings API."""
    try:
        response = client.embeddings.create(
            model='text-embedding-3-small',
            input=text
        )
        embedding = response.data[0].embedding
        # Convert to binary for storage
        embedding_blob = json.dumps(embedding).encode('utf-8')
        return embedding_blob
    except Exception as e:
        print(f"❌ Error creating embedding: {e}")
        raise

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
    except Exception as e:
        print(f"❌ Error calculating similarity: {e}")
        return 0.0

def process_video(video_path, filename):
    """Process video: extract audio, transcribe, create embeddings, and store."""
    print(f"\n{'='*60}")
    print(f"🎬 PROCESSING VIDEO: {filename}")
    print(f"{'='*60}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get video duration
        video_duration = get_video_duration(video_path)
        print(f"⏱️  Video duration: {video_duration:.2f}s")
        
        # Generate thumbnail (at 1 second or 10% into video, whichever is smaller)
        thumbnail_time = min(1.0, video_duration * 0.1)
        thumbnail_filename = f"thumb_{os.path.splitext(filename)[0]}.jpg"
        thumbnail_path = os.path.join(THUMBNAILS_FOLDER, thumbnail_filename)
        generate_thumbnail(video_path, thumbnail_path, thumbnail_time)
        
        # Insert video record
        cursor.execute('''
            INSERT INTO videos (filename, duration, status, thumbnail)
            VALUES (?, ?, 'processing', ?)
        ''', (filename, video_duration, thumbnail_filename))
        video_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Video record created (ID: {video_id})")
        
        # Extract audio
        print("\n🔊 Step 1: Extracting audio...")
        audio_path = extract_audio(video_path)
        
        segment_count = 0
        
        if audio_path:
            try:
                # Transcribe
                print("\n🎤 Step 2: Transcribing with Whisper...")
                transcript = transcribe_audio(audio_path)
                
                # Process segments and create embeddings
                print(f"\n🧠 Step 3: Creating embeddings for {len(transcript.segments)} segments...")
                
                for i, segment in enumerate(transcript.segments):
                    start_time = segment.start
                    end_time = segment.end
                    text = segment.text.strip()
                    
                    if not text:
                        continue
                    
                    segment_count += 1
                    print(f"  📝 Segment {segment_count}/{len(transcript.segments)}: {text[:60]}...")
                    
                    # Create combined text with metadata for embedding
                    # Extract clean title from filename
                    clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
                    combined_text_audio = f"Title: {clean_title}. Transcript: {text}"
                    
                    print(f"     🧠 Creating embedding with title metadata...")
                    embedding_blob = create_embedding(combined_text_audio)
                    
                    # Store in database
                    cursor.execute('''
                        INSERT INTO clips (video_id, filename, start_time, end_time, duration, transcript_text, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        video_id,
                        filename,
                        start_time,
                        end_time,
                        min(CHUNK_DURATION, end_time - start_time),
                        text,
                        embedding_blob
                    ))
                    print(f"     ✅ Stored in database")
                
            except Exception as e:
                import traceback
                print(f"⚠️  Audio transcription error: {e}")
                print(traceback.format_exc())
            
            finally:
                # Clean up temporary audio file
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    print("🧹 Cleaned up temporary audio file")
        else:
            print("\n⚠️  No audio track found - Skipping transcription (normal for GIFs/silent videos)")
        
        # Step 4: Visual Analysis (ALWAYS RUN - for both videos and GIFs)
        print(f"\n🎨 Step 4: Visual content analysis...")
        frames = extract_frames_for_analysis(video_path, video_duration, filename)
        
        # GET TRANSCRIPT FOR THIS VIDEO (for context-rich visual descriptions)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT transcript_text FROM clips WHERE video_id = ? ORDER BY start_time', (video_id,))
        transcript_rows = cursor.fetchall()
        full_transcript = ' '.join([row[0] for row in transcript_rows if row[0]]) if transcript_rows else ''
        conn.close()
        print(f"📝 Transcript loaded: {len(full_transcript)} characters")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        visual_count = 0
        for frame_data in frames:
            print(f"  🔍 Analyzing frame at {frame_data['timestamp']}s...")
            
            # Get transcript segment near this timestamp (±10s window)
            cursor.execute('''
                SELECT transcript_text FROM clips 
                WHERE video_id = ? 
                AND start_time <= ? 
                AND end_time >= ?
                ORDER BY start_time
                LIMIT 3
            ''', (video_id, frame_data['timestamp'] + 10, frame_data['timestamp'] - 10))
            
            nearby_transcripts = cursor.fetchall()
            context_transcript = ' '.join([row[0] for row in nearby_transcripts if row[0]])
            
            # Analyze frame with Vision API + transcript context + filename hint
            analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context_transcript, filename_hint=filename)
            
            if analysis:
                # Extract ALL metadata from analysis with SAFE TYPE CONVERSION
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
                
                # Extract CATEGORIZED TAGS (5 categories) - Convert arrays to comma-separated strings
                def parse_tag_array(tag_data):
                    """Convert tag array/list to comma-separated string"""
                    if isinstance(tag_data, list):
                        return ', '.join(str(tag) for tag in tag_data if tag)
                    elif isinstance(tag_data, str):
                        return tag_data
                    else:
                        return str(tag_data) if tag_data else ''
                
                emotion_tags = parse_tag_array(analysis.get('emotion_tags', ''))
                laugh_tags = parse_tag_array(analysis.get('laugh_tags', ''))
                contextual_tags = parse_tag_array(analysis.get('contextual_tags', ''))
                character_tags = parse_tag_array(analysis.get('character_tags', ''))
                semantic_tags = parse_tag_array(analysis.get('semantic_tags', ''))
                
                # FALLBACK: If Vision API didn't return categorized tags, INTELLIGENTLY GENERATE them
                if not emotion_tags and not laugh_tags and not contextual_tags:
                    print(f"     ⚠️  Vision API didn't return categorized tags - intelligently generating from analysis...")
                    generated = intelligently_generate_categorized_tags(analysis)
                    emotion_tags = generated['emotion_tags']
                    laugh_tags = generated['laugh_tags']
                    contextual_tags = generated['contextual_tags']
                    character_tags = generated['character_tags']
                    semantic_tags = generated['semantic_tags']
                    print(f"     ✅ Generated {generated['total_count']} tags: Emotion={generated['counts']['emotion']}, Laugh={generated['counts']['laugh']}, Context={generated['counts']['contextual']}, Char={generated['counts']['character']}, Semantic={generated['counts']['semantic']}")
                
                
                print(f"     📝 Description: {description[:80]}...")
                if actors:
                    print(f"     🎭 Actors: {actors}")
                
                # Extract clean title from filename for metadata
                clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
                
                # Create COMPREHENSIVE embedding text with ALL metadata including categorized tags
                combined_text = f"Title: {clean_title}. {description}. Emotion: {emotion}."
                if deep_emotions:
                    combined_text += f" Deep Emotions: {deep_emotions}."
                if scene_context:
                    combined_text += f" Scene: {scene_context}."
                if people_description:
                    combined_text += f" People: {people_description}."
                if environment:
                    combined_text += f" Environment: {environment}."
                if dialogue_context:
                    combined_text += f" Dialogue: {dialogue_context}."
                if series_movie:
                    combined_text += f" Series/Movie: {series_movie}."
                if ocr_text:
                    combined_text += f" Text on screen: {ocr_text}."
                if tags:
                    combined_text += f" Tags: {tags}."
                if emotion_tags:
                    combined_text += f" Emotion Tags: {emotion_tags}."
                if laugh_tags:
                    combined_text += f" Laugh Tags: {laugh_tags}."
                if contextual_tags:
                    combined_text += f" Context: {contextual_tags}."
                if character_tags:
                    combined_text += f" Characters: {character_tags}."
                if semantic_tags:
                    combined_text += f" Semantic: {semantic_tags}."
                if genres:
                    combined_text += f" Genres: {genres}."
                
                # Create embedding from comprehensive metadata
                print(f"     🧠 Creating visual embedding with comprehensive metadata...")
                visual_embedding = create_embedding(combined_text)
                
                # Store visual data with ALL fields (basic + advanced tagging + categorized tags)
                cursor.execute('''
                    INSERT INTO visual_frames (
                        video_id, filename, timestamp, frame_path, visual_description, visual_embedding, 
                        emotion, ocr_text, tags, genres,
                        deep_emotions, scene_context, people_description, environment, 
                        dialogue_context, series_movie, target_audience, scene_type, actors, media_type,
                        emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video_id,
                    filename,
                    frame_data['timestamp'],
                    frame_data['filename'],
                    description,
                    visual_embedding,
                    emotion,
                    ocr_text,
                    tags,
                    genres,
                    deep_emotions,
                    scene_context,
                    people_description,
                    environment,
                    dialogue_context,
                    series_movie,
                    target_audience,
                    scene_type,
                    actors,
                    media_type,
                    emotion_tags,
                    laugh_tags,
                    contextual_tags,
                    character_tags,
                    semantic_tags
                ))
                visual_count += 1
                print(f"     ✅ Visual data stored")
        
        # Update video status to complete
        cursor.execute('''
            UPDATE videos SET status = 'complete' WHERE id = ?
        ''', (video_id,))
        conn.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ VIDEO PROCESSING COMPLETE!")
        print(f"   - {segment_count} audio clips created")
        print(f"   - {visual_count} visual frames analyzed")
        print(f"   - Multi-modal embeddings stored")
        print(f"   - Ready for visual + audio search")
        print(f"{'='*60}\n")
    
    except Exception as e:
        # Mark video as failed
        cursor.execute('''
            UPDATE videos SET status = 'failed' WHERE id = ?
        ''', (video_id,))
        conn.commit()
        print(f"\n❌ VIDEO PROCESSING FAILED: {e}")
        raise
    finally:
        conn.close()

@app.route('/')
def index():
    return send_from_directory('.', 'index_semantic.html')

@app.route('/index_semantic.html')
def index_semantic():
    return send_from_directory('.', 'index_semantic.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("\n" + "="*60)
    print("📤 UPLOAD REQUEST RECEIVED")
    print("="*60)
    
    if 'file' not in request.files:
        print("❌ No file in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    print(f"📁 File received: {file.filename}")
    
    if file.filename == '':
        print("❌ Empty filename")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        print(f"💾 Saving to: {filepath}")
        
        # Check if file already exists in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM videos WHERE filename = ?', (filename,))
        existing_video = cursor.fetchone()
        
        if existing_video:
            print(f"⚠️  Video already exists in database: {filename}")
            print(f"   Deleting existing record and re-uploading...")
            
            # Delete existing video record and all associated data
            video_id = existing_video[0]
            cursor.execute('DELETE FROM clips WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM visual_frames WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
            conn.commit()
            print(f"   ✅ Existing record deleted")
        
        conn.close()
        
        # Save file (overwrite if exists)
        file.save(filepath)
        print(f"✅ File saved successfully")
        
        try:
            # Process video
            process_video(filepath, filename)
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"❌ ERROR during processing:\n{error_detail}")
            return jsonify({'error': str(e)}), 500
    
    print(f"❌ Invalid file type for {file.filename}")
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/search', methods=['POST'])
def search():
    print("\n" + "="*60)
    print("🔍 MULTI-MODAL SEARCH REQUEST")
    print("="*60)
    
    data = request.json
    query = data.get('query', '').strip()
    emotions_filter = data.get('emotions', [])  # List of selected emotions
    genres_filter = data.get('genres', [])  # List of selected genres
    
    # Allow filter-only search (no query text required)
    if not query and not emotions_filter and not genres_filter:
        print("❌ Empty query and no filters")
        return jsonify({'results': []})
    
    print(f"🔎 Query: \"{query}\"")
    if emotions_filter:
        print(f"🎭 Emotion Filters: {emotions_filter}")
    if genres_filter:
        print(f"🎬 Genre Filters: {genres_filter}")
    
    try:
        # Create embedding for search query (only if query exists)
        query_embedding = None
        detected_series = None
        if query:
            print("🧠 Creating query embedding...")
            query_embedding = create_embedding(query)
            
            # DETECT SERIES/MOVIE NAME IN QUERY for filtering
            query_lower = query.lower()
            known_series = [
                # Indian Web Series
                'farzi', 'scam 1992', 'scam', 'mirzapur', 'sacred games', 'the family man',
                'delhi crime', 'paatal lok', 'breathe', 'asur', 'panchayat', 'kota factory',
                'made in heaven', 'four more shots please', 'bandish bandits',
                
                # Bollywood Movies (Aamir Khan)
                '3 idiots', '3-idiots', 'pk', 'dangal', 'taare zameen par', 'lagaan',
                'rang de basanti', 'dil chahta hai', 'ghajini', 'fanaa',
                
                # Bollywood Movies (Shah Rukh Khan)
                'dilwale dulhania le jayenge', 'ddlj', 'kuch kuch hota hai', 'kkh',
                'kabhi khushi kabhie gham', 'k3g', 'swades', 'chak de india', 'my name is khan',
                'chennai express', 'raees', 'zero',
                
                # Bollywood Movies (Other Stars)
                'highway', 'raazi', 'gangubai', 'gangubai kathiawadi', 'alia bhatt',
                'barfi', 'chhichhore', 'student of the year', 'yeh jawaani hai deewani',
                'wake up sid', 'dil dhadakne do', 'gully boy', 'zindagi na milegi dobara',
                'znmd', 'kabir singh', 'arjun reddy', 'padmaavat', 'bajirao mastani',
                'ram leela', 'udta punjab', 'andhadhun', 'article 15', 'pink',
                'jolly llb', 'stree', 'badhaai ho', 'vicky donor',
                
                # Rocket Singh and Similar Office/Workplace Movies
                'rocket singh', 'rocket singh salesman of the year', 'guru', 'guru 2007',
                'hindi medium', 'english medium', 'piku', 'october', 'masaan',
                
                # Rajkumar Hirani Films
                'munna bhai mbbs', 'lage raho munna bhai', 'sanju',
                
                # Crime/Thriller Bollywood
                'gangs of wasseypur', 'gow', 'kahaani', 'drishyam', 'talvar', 'special 26',
                'baby', 'madras cafe', 'rahasya', 'badla', 'ittefaq',
                
                # Hollywood Movies
                'the office', 'breaking bad', 'friends', 'wolf of wall street',
                'the intern', 'legally blonde', 'ratatouille', 'the imitation game',
                'inception', 'interstellar', 'the dark knight', 'shawshank redemption',
                'fight club', 'the godfather', 'pulp fiction', 'forrest gump',
                'the social network', 'steve jobs', 'the pursuit of happyness',
                'good will hunting', 'dead poets society', 'moneyball'
            ]
            
            # Check if query contains a known series/movie name
            for series in known_series:
                if series in query_lower:
                    detected_series = series
                    print(f"🎬 Detected series/movie filter: '{detected_series}' - will filter out other series!")
                    break
            
            # DETECT GENDER/PEOPLE FILTERS IN QUERY
            detected_gender = None
            detected_count = None
            gender_keywords = {
                'woman': ['woman', 'women', 'female', 'lady', 'ladies', 'girl', 'girls'],
                'man': ['man', 'men', 'male', 'guy', 'guys', 'boy', 'boys'],
                'child': ['child', 'children', 'kid', 'kids', 'baby', 'babies'],
                'couple': ['couple', 'pair', 'duo'],
                'group': ['group', 'people', 'crowd']
            }
            
            # Check for gender/people keywords in query
            for gender_type, keywords in gender_keywords.items():
                for keyword in keywords:
                    # Use word boundaries to avoid partial matches (e.g., "women" shouldn't match "moment")
                    if f' {keyword} ' in f' {query_lower} ' or query_lower.startswith(keyword + ' ') or query_lower.endswith(' ' + keyword) or query_lower == keyword:
                        detected_gender = gender_type
                        print(f"👥 Detected gender/people filter: '{gender_type}' (from keyword: '{keyword}') - will validate people descriptions!")
                        break
                if detected_gender:
                    break
            
            # DETECT NUMBER OF PEOPLE IN QUERY (e.g., "two men", "three women")
            number_keywords = {
                'one': 1, 'single': 1, 'solo': 1,
                'two': 2, 'couple': 2, 'pair': 2, 'duo': 2,
                'three': 3, 'trio': 3,
                'four': 4, 'quartet': 4,
                'five': 5,
                'many': None, 'multiple': None, 'several': None, 'group': None
            }
            for num_word, count in number_keywords.items():
                if num_word in query_lower.split():
                    detected_count = count
                    print(f"🔢 Detected people count: '{num_word}' ({count}) - will validate number of people!")
                    break
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        results = []
        
        # If filter-only search (no query), fetch all visual frames for filtering
        if not query and (emotions_filter or genres_filter):
            print(f"🎨 Fetching all visual content for filter-only search...")
            cursor.execute('''SELECT vf.id, vf.video_id, vf.filename, vf.timestamp, vf.visual_description, vf.visual_embedding, 
                                     vf.emotion, vf.ocr_text, vf.tags, vf.genres, vf.deep_emotions, vf.scene_context, 
                                     vf.people_description, vf.environment, vf.series_movie, vf.actors, v.custom_tags,
                                     vf.emotion_tags, vf.laugh_tags, vf.contextual_tags, vf.character_tags, vf.semantic_tags
                              FROM visual_frames vf
                              LEFT JOIN videos v ON vf.video_id = v.id''')
            
            for row in cursor.fetchall():
                frame_id, video_id, filename, timestamp, description, embedding_blob, emotion, ocr_text, tags, genres, deep_emotions, scene_context, people_description, environment, series_movie, actors, custom_tags, emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags = row
                
                # Build display text with emotion and OCR
                display_text = f"[Visual] {description}"
                if emotion and emotion != 'neutral':
                    display_text = f"[Visual - {emotion.title()}] {description}"
                if ocr_text:
                    display_text += f" | Text: \"{ocr_text}\""
                
                results.append({
                    'id': f"visual_{frame_id}",
                    'video_id': video_id,
                    'filename': filename,
                    'timestamp': timestamp,
                    'start_time': timestamp,
                    'end_time': timestamp + 10,
                    'duration': 10.0,
                    'text': display_text,
                    'similarity': 1.0,  # Max similarity for filter-only
                    'source': 'visual',
                    'emotion': emotion or 'neutral',
                    'ocr_text': ocr_text or '',
                    'tags': tags or '',
                    'genres': genres or '',
                    'custom_tags': custom_tags or '',
                    'emotion_tags': emotion_tags or '',
                    'laugh_tags': laugh_tags or '',
                    'contextual_tags': contextual_tags or '',
                    'character_tags': character_tags or '',
                    'semantic_tags': semantic_tags or ''
                })
        
        # Search in audio transcripts (only if query exists)
        elif query:
            print(f"🎤 Searching audio transcripts...")
            cursor.execute('SELECT id, video_id, filename, start_time, end_time, duration, transcript_text, embedding FROM clips')
            
            for row in cursor.fetchall():
                clip_id, video_id, filename, start_time, end_time, duration, text, embedding_blob = row
                
                # Calculate semantic similarity
                similarity = cosine_similarity(query_embedding, embedding_blob)
                
                # RELEVANCE BOOST: If query text appears in transcript, boost similarity
                query_lower = query.lower()
                text_lower = text.lower()
                exact_match_boost = 0.0
                if len(query_lower) > 3 and query_lower in text_lower:
                    exact_match_boost = 0.35  # +35% boost for exact transcript match
                
                boosted_similarity = min(1.0, similarity + exact_match_boost)
                
                # RAISED THRESHOLD: Only show relevant results (40% minimum)
                # Skip music-only clips for better relevance
                min_threshold = 0.40
                
                if boosted_similarity > min_threshold:
                    # Skip pure music clips unless query is about music/sound/audio
                    # Check for various music notation patterns
                    is_music_only = text.strip() in ['♪', '♪♪', '♪♪♪', '🎵', '🎶', '[Music]', '(Music)', '...']
                    is_music_query = any(word in query.lower() for word in ['music', 'song', 'audio', 'sound', 'beat', 'melody'])
                    
                    if is_music_only and not is_music_query:
                        continue
                        
                    results.append({
                        'id': f"audio_{clip_id}",
                        'video_id': video_id,
                        'filename': filename,
                        'timestamp': start_time,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': duration,
                        'text': text,
                        'similarity': float(boosted_similarity),  # Use boosted score
                        'source': 'audio'
                    })
            
            # Search in visual frames (with all metadata fields) - only if query exists
            print(f"🎨 Searching visual content...")
            cursor.execute('''SELECT vf.id, vf.video_id, vf.filename, vf.timestamp, vf.visual_description, vf.visual_embedding, 
                                     vf.emotion, vf.ocr_text, vf.tags, vf.genres, vf.deep_emotions, vf.scene_context, 
                                     vf.people_description, vf.environment, vf.series_movie, vf.actors, v.custom_tags,
                                     vf.emotion_tags, vf.laugh_tags, vf.contextual_tags, vf.character_tags, vf.semantic_tags
                              FROM visual_frames vf
                              LEFT JOIN videos v ON vf.video_id = v.id''')
            
            for row in cursor.fetchall():
                frame_id, video_id, filename, timestamp, description, embedding_blob, emotion, ocr_text, tags, genres, deep_emotions, scene_context, people_description, environment, series_movie, actors, custom_tags, emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags = row
                
                # Calculate semantic similarity
                similarity = cosine_similarity(query_embedding, embedding_blob)
                
                # ENHANCED RELEVANCE BOOST with CUSTOM TAGS & ACTOR-SPECIFIC LOGIC
                query_lower = query.lower()
                
                # Check if query appears in any metadata (prioritized by importance)
                exact_match_boost = 0.0
                if len(query_lower) > 2:  # Lower threshold for actor names
                    # CUSTOM TAGS (HIGHEST PRIORITY - User explicitly added these!)
                    if custom_tags and query_lower in custom_tags.lower():
                        exact_match_boost = max(exact_match_boost, 0.50)  # Strongest boost
                    
                    # ACTOR NAME MATCHING (Very High Priority)
                    # Check for partial matches too (e.g., "Shahid" matches "Shahid Kapoor")
                    if actors:
                        actors_lower = actors.lower()
                        # Exact full match
                        if query_lower in actors_lower:
                            exact_match_boost = max(exact_match_boost, 0.45)
                        # Partial name match (first/last name)
                        else:
                            query_parts = query_lower.split()
                            for part in query_parts:
                                if len(part) > 3 and part in actors_lower:
                                    exact_match_boost = max(exact_match_boost, 0.42)
                                    break
                    
                    # SERIES/MOVIE NAME (Very High Priority)
                    if series_movie and query_lower in series_movie.lower():
                        exact_match_boost = max(exact_match_boost, 0.40)
                    
                    # DESCRIPTION (High Priority)
                    if description and query_lower in description.lower():
                        exact_match_boost = max(exact_match_boost, 0.35)
                    
                    # DEEP EMOTIONS (Medium-High)
                    if deep_emotions and query_lower in deep_emotions.lower():
                        exact_match_boost = max(exact_match_boost, 0.32)
                    
                    # OCR TEXT (Medium-High)
                    if ocr_text and query_lower in ocr_text.lower():
                        exact_match_boost = max(exact_match_boost, 0.30)
                    
                    # SCENE CONTEXT (Medium)
                    if scene_context and query_lower in scene_context.lower():
                        exact_match_boost = max(exact_match_boost, 0.28)
                    
                    # TAGS (Standard) - Check OLD tags field
                    if tags and query_lower in tags.lower():
                        exact_match_boost = max(exact_match_boost, 0.25)
                    
                    # NEW CATEGORIZED TAGS (High Priority - User's primary search target!)
                    # Normalize query for tag matching (remove hyphens, underscores)
                    normalized_query = query_lower.replace('-', ' ').replace('_', ' ').strip()
                    
                    # SYNONYM EXPANSION for common words
                    query_synonyms = {
                        'bro': ['brother', 'brotherhood', 'bromance', 'bro'],
                        'brother': ['brother', 'brotherhood', 'bromance', 'sibling', 'bro'],
                        'brothers': ['brother', 'brotherhood', 'bromance', 'sibling', 'bro'],
                        'friend': ['friend', 'friendship', 'buddy', 'pal', 'companion'],
                        'friends': ['friend', 'friendship', 'buddy', 'pal', 'companion'],
                        'man': ['man', 'male', 'men', 'guy'],
                        'men': ['man', 'male', 'men', 'guy', 'guys', 'duo', 'two-men', 'three-men'],
                        'woman': ['woman', 'female', 'women', 'lady'],
                        'women': ['woman', 'female', 'women', 'lady', 'ladies', 'duo'],
                        'guy': ['guy', 'man', 'male', 'dude'],
                        'guys': ['guy', 'guys', 'men', 'males', 'dudes'],
                        'duo': ['duo', 'pair', 'two', 'couple', 'twosome'],
                        'pair': ['pair', 'duo', 'two', 'couple', 'twosome'],
                        'money': ['money', 'cash', 'currency', 'wealth', 'riches'],
                        'cash': ['cash', 'money', 'currency', 'bills'],
                        'happy': ['happy', 'joy', 'happiness', 'joyful', 'cheerful'],
                        'sad': ['sad', 'sadness', 'sorrow', 'melancholy', 'grief']
                    }
                    
                    # Expand query with synonyms
                    query_words = normalized_query.split()
                    expanded_words = set(query_words)  # Start with original words
                    for word in query_words:
                        if word in query_synonyms:
                            expanded_words.update(query_synonyms[word])
                    
                    # Helper function to check tag match (with normalization + partial word matching)
                    def tag_matches(tag_field, search_terms_set):
                        if not tag_field:
                            return False
                        # Normalize tags (remove hyphens, underscores, commas)
                        normalized_tags = tag_field.lower().replace('-', ' ').replace('_', ' ').replace(',', ' ')
                        tag_words = normalized_tags.split()
                        
                        # Check if ALL query words match ANY tag word (partial match OK)
                        # Example: "two brother" matches if "two" is in any tag AND "brother" is in any tag
                        query_word_list = list(search_terms_set)
                        
                        # EXACT PHRASE MATCH (highest priority)
                        search_phrase = ' '.join(query_word_list[:2] if len(query_word_list) > 1 else query_word_list)
                        if search_phrase in normalized_tags:
                            return True
                        
                        # PARTIAL WORD MATCH (each query word matches at least one tag word)
                        for query_word in query_word_list:
                            matched = False
                            for tag_word in tag_words:
                                # Exact word match OR partial match (for "bro" matching "bromance")
                                if query_word == tag_word or query_word in tag_word or tag_word in query_word:
                                    matched = True
                                    break
                            if matched:
                                return True  # At least one word matched
                        
                        return False
                    
                    # Check all categorized tag fields (with synonym expansion + partial matching)
                    if emotion_tags and tag_matches(emotion_tags, expanded_words):
                        exact_match_boost = max(exact_match_boost, 0.45)  # Increased boost!
                    
                    if laugh_tags and tag_matches(laugh_tags, expanded_words):
                        exact_match_boost = max(exact_match_boost, 0.45)  # Increased boost!
                    
                    if contextual_tags and tag_matches(contextual_tags, expanded_words):
                        exact_match_boost = max(exact_match_boost, 0.43)  # Increased boost!
                    
                    if character_tags and tag_matches(character_tags, expanded_words):
                        exact_match_boost = max(exact_match_boost, 0.43)  # Increased boost!
                    
                    if semantic_tags and tag_matches(semantic_tags, expanded_words):
                        exact_match_boost = max(exact_match_boost, 0.40)  # Increased boost!
                    
                    # SEMANTIC TAG MATCHING: "evil laugh" → "mischief laugh", "villainous laugh", etc.
                    # Check if query contains emotion/laugh keywords, then find related tags
                    if not exact_match_boost or exact_match_boost < 0.30:  # Only if no exact match found
                        semantic_matches = []
                        
                        # Emotion/Laugh keyword mapping for semantic search
                        emotion_synonyms = {
                            'evil': ['villainous', 'sinister', 'menacing', 'malicious', 'wicked', 'dark', 'mischief', 'criminal', 'manipulative'],
                            'happy': ['joy', 'joyful', 'cheerful', 'content', 'pleased', 'satisfied', 'delighted', 'euphoric'],
                            'sad': ['melancholy', 'sorrowful', 'heartbroken', 'dejected', 'gloomy', 'depressed', 'tearful'],
                            'angry': ['furious', 'enraged', 'irate', 'livid', 'wrathful', 'hostile', 'rage'],
                            'laugh': ['chuckle', 'giggle', 'cackle', 'guffaw', 'snicker', 'chortle', 'smile'],
                            'scared': ['fearful', 'terrified', 'frightened', 'panicked', 'anxious', 'nervous'],
                            'excited': ['thrilled', 'exhilarated', 'energized', 'pumped', 'hyped', 'ecstatic'],
                            'calm': ['peaceful', 'serene', 'tranquil', 'relaxed', 'composed', 'content'],
                            'crazy': ['wild', 'chaotic', 'manic', 'unhinged', 'mad', 'frenzied', 'delirious'],
                            'victory': ['triumphant', 'successful', 'winning', 'champion', 'conquest'],
                            'crime': ['criminal', 'illegal', 'unlawful', 'illicit', 'heist', 'con'],
                            'money': ['cash', 'wealth', 'riches', 'currency', 'financial']
                        }
                        
                        # Check if any synonym appears in tags
                        query_words = normalized_query.split()
                        for word in query_words:
                            if word in emotion_synonyms:
                                synonyms = emotion_synonyms[word]
                                # Check all tag fields for synonyms
                                all_tags = f"{emotion_tags} {laugh_tags} {contextual_tags} {character_tags} {semantic_tags}".lower()
                                for synonym in synonyms:
                                    if synonym in all_tags:
                                        semantic_matches.append(synonym)
                                        break
                        
                        # Apply semantic match boost (lower than exact, but still significant)
                        if semantic_matches:
                            exact_match_boost = max(exact_match_boost, 0.25)  # Boost for semantic tag match
                
                # Apply boost
                boosted_similarity = min(1.0, similarity + exact_match_boost)
                
                # SERIES/MOVIE FILTERING: If specific series detected in query, filter out other series
                if detected_series:
                    series_lower = series_movie.lower() if series_movie else ''
                    
                    # STRICT FILTERING: When user searches for specific movie, ONLY show that movie
                    # Skip if:
                    # 1. Series is unknown/empty (AI didn't detect the movie)
                    # 2. Series doesn't match the searched movie
                    
                    if not series_lower or detected_series not in series_lower:
                        # Skip this result - it's either Unknown or from a different movie
                        print(f"   ⚠️ Skipping result - User searched '{detected_series}' but video is from '{series_movie or 'Unknown'}'")
                        continue  # Skip to next result
                
                # GENDER/PEOPLE FILTERING: If gender/people keyword detected, validate people descriptions
                if detected_gender:
                    people_desc_lower = people_description.lower() if people_description else ''
                    description_lower = description.lower() if description else ''
                    actors_lower = actors.lower() if actors else ''
                    
                    # Combine all people-related fields for validation
                    combined_people_text = f"{people_desc_lower} {description_lower} {actors_lower}"
                    
                    gender_valid = False
                    
                    if detected_gender == 'woman':
                        # Must contain woman/women/female/lady/girl AND NOT contain man/men/male/guy/boy
                        has_woman = any(word in combined_people_text for word in ['woman', 'women', 'female', 'lady', 'ladies', 'girl', 'actress'])
                        has_man = any(word in combined_people_text for word in ['man ', 'men ', 'male', ' guy', 'guys', ' boy', 'boys', 'actor'])
                        
                        # Valid if has woman keywords AND no man keywords (unless it's a mixed group explicitly mentioned)
                        gender_valid = has_woman and not has_man
                        
                        # Also check known female actors
                        female_actors = ['alia bhatt', 'deepika padukone', 'priyanka chopra', 'kareena kapoor', 
                                       'katrina kaif', 'anushka sharma', 'vidya balan', 'kangana ranaut',
                                       'margot robbie', 'scarlett johansson', 'jennifer lawrence', 'emma stone',
                                       'anne hathaway', 'reese witherspoon']
                        if any(actress in actors_lower for actress in female_actors):
                            gender_valid = True
                    
                    elif detected_gender == 'man':
                        # Must contain man/men/male/guy/boy AND NOT contain woman/women/female/lady/girl
                        has_man = any(word in combined_people_text for word in ['man ', 'men ', 'male', ' guy', 'guys', ' boy', 'boys', 'actor'])
                        has_woman = any(word in combined_people_text for word in ['woman', 'women', 'female', 'lady', 'ladies', 'girl', 'actress'])
                        
                        gender_valid = has_man and not has_woman
                        
                        # Also check known male actors
                        male_actors = ['shah rukh khan', 'aamir khan', 'salman khan', 'shahid kapoor', 'ranbir kapoor',
                                     'ranveer singh', 'hrithik roshan', 'ayushmann khurrana', 'rajkummar rao',
                                     'leonardo dicaprio', 'brad pitt', 'tom cruise', 'robert downey', 'chris hemsworth']
                        if any(actor in actors_lower for actor in male_actors):
                            gender_valid = True
                    
                    elif detected_gender == 'child':
                        # Must contain child/kid/baby keywords
                        gender_valid = any(word in combined_people_text for word in ['child', 'children', 'kid', 'kids', 'baby', 'babies', 'toddler', 'infant'])
                    
                    elif detected_gender == 'couple':
                        # Must contain couple/pair/duo keywords or mention two people
                        gender_valid = any(word in combined_people_text for word in ['couple', 'pair', 'duo', 'two people', 'two men', 'two women', 'man and woman'])
                    
                    elif detected_gender == 'group':
                        # Must contain group/crowd/people keywords
                        gender_valid = any(word in combined_people_text for word in ['group', 'crowd', 'people', 'several', 'multiple', 'many', 'gathering'])
                    
                    # Skip this result if gender doesn't match
                    if not gender_valid:
                        continue  # Skip to next result
                
                # NUMBER OF PEOPLE FILTERING: If count detected, validate number of people
                if detected_count is not None:
                    people_desc_lower = people_description.lower() if people_description else ''
                    description_lower = description.lower() if description else ''
                    
                    combined_text = f"{people_desc_lower} {description_lower}"
                    
                    count_valid = False
                    
                    if detected_count == 1:
                        # Must mention "one person", "solo", "single", "a man", "a woman" (singular)
                        singular_keywords = ['one ', 'single ', 'solo ', 'a man', 'a woman', 'a person', 'a child', 'alone']
                        count_valid = any(keyword in combined_text for keyword in singular_keywords)
                        # Also valid if it explicitly says NOT multiple people
                        if not count_valid:
                            count_valid = not any(word in combined_text for word in ['two ', 'three ', 'four ', 'multiple', 'several', 'group', 'couple', 'pair'])
                    
                    elif detected_count == 2:
                        # Must mention "two", "couple", "pair", "duo"
                        two_keywords = ['two ', 'couple', 'pair', 'duo']
                        count_valid = any(keyword in combined_text for keyword in two_keywords)
                    
                    elif detected_count == 3:
                        # Must mention "three", "trio"
                        three_keywords = ['three ', 'trio']
                        count_valid = any(keyword in combined_text for keyword in three_keywords)
                    
                    elif detected_count == 4:
                        # Must mention "four", "quartet"
                        four_keywords = ['four ', 'quartet']
                        count_valid = any(keyword in combined_text for keyword in four_keywords)
                    
                    # Skip if count doesn't match
                    if not count_valid:
                        continue  # Skip to next result
                
                # ACTION/ACTIVITY VALIDATION: If query mentions action, validate it's actually happening
                action_keywords = {
                    'hug': ['hug', 'hugging', 'embrace', 'embracing', 'holding'],
                    'kiss': ['kiss', 'kissing', 'romantic'],
                    'fight': ['fight', 'fighting', 'punch', 'combat', 'hitting'],
                    'dance': ['dance', 'dancing', 'choreography'],
                    'run': ['run', 'running', 'chase', 'chasing'],
                    'cry': ['cry', 'crying', 'tears', 'weeping', 'sobbing'],
                    'laugh': ['laugh', 'laughing', 'chuckle', 'giggle'],
                    'eat': ['eat', 'eating', 'dining', 'food'],
                    'drink': ['drink', 'drinking', 'beverage'],
                    'drive': ['drive', 'driving', 'car', 'vehicle'],
                    'walk': ['walk', 'walking'],
                    'sit': ['sit', 'sitting', 'seated'],
                    'stand': ['stand', 'standing'],
                    'talk': ['talk', 'talking', 'conversation', 'speaking'],
                    'shout': ['shout', 'shouting', 'yelling', 'scream'],
                    'whisper': ['whisper', 'whispering']
                }
                
                detected_action = None
                for action, action_variants in action_keywords.items():
                    for variant in action_variants:
                        # Word boundary check
                        if f' {variant} ' in f' {query_lower} ' or query_lower.startswith(variant + ' ') or query_lower.endswith(' ' + variant) or query_lower == variant:
                            detected_action = action
                            print(f"🎬 Detected action filter: '{action}' - will validate this action is visible!")
                            break
                    if detected_action:
                        break
                
                if detected_action:
                    desc_lower = description.lower() if description else ''
                    tags_combined = f"{tags} {contextual_tags} {emotion_tags}".lower()
                    
                    action_valid = False
                    action_check_variants = action_keywords[detected_action]
                    
                    # Check if ANY variant of the action appears in description or tags
                    for variant in action_check_variants:
                        if variant in desc_lower or variant in tags_combined:
                            action_valid = True
                            break
                    
                    # IMPORTANT: Only filter if we have good description data
                    # If description is too short/empty, don't filter (Vision API might have failed)
                    has_good_data = len(desc_lower) > 50 and desc_lower != 'video frame'
                    
                    # Skip if action is not present AND we have good data to validate against
                    if not action_valid and has_good_data:
                        print(f"   ⚠️ Skipping result - '{detected_action}' not found in video")
                        continue  # Skip to next result
                    elif not action_valid and not has_good_data:
                        print(f"   ⚠️ '{detected_action}' not found, but description is incomplete - including result anyway")
                        # Allow result through since we can't reliably validate
                
                # OBJECT/VISUAL ELEMENT VALIDATION: If query mentions specific objects, validate they're present
                object_keywords = {
                    # Clothing/Headwear
                    'turban': ['turban', 'sikh', 'dastar', 'pagri', 'headwrap'],
                    'hat': ['hat', 'cap', 'beanie', 'fedora'],
                    'helmet': ['helmet', 'headgear'],
                    'sunglasses': ['sunglasses', 'shades', 'glasses'],
                    'suit': ['suit', 'formal', 'blazer', 'tuxedo'],
                    'saree': ['saree', 'sari', 'traditional'],
                    'uniform': ['uniform', 'police', 'military', 'officer'],
                    
                    # Objects
                    'car': ['car', 'vehicle', 'automobile', 'driving'],
                    'bike': ['bike', 'motorcycle', 'bicycle', 'cycling'],
                    'phone': ['phone', 'mobile', 'smartphone', 'cellphone', 'calling'],
                    'laptop': ['laptop', 'computer', 'notebook'],
                    'gun': ['gun', 'weapon', 'pistol', 'rifle', 'firearm'],
                    'money': ['money', 'cash', 'currency', 'bills', 'notes', 'rupees'],
                    'book': ['book', 'reading', 'novel', 'textbook'],
                    'camera': ['camera', 'filming', 'photography'],
                    'cigarette': ['cigarette', 'smoking', 'smoke'],
                    'drink': ['drink', 'glass', 'cup', 'bottle', 'beverage'],
                    'food': ['food', 'eating', 'meal', 'dish', 'plate'],
                    
                    # Settings/Places
                    'office': ['office', 'desk', 'workplace', 'corporate'],
                    'classroom': ['classroom', 'school', 'college', 'blackboard'],
                    'hospital': ['hospital', 'clinic', 'medical', 'doctor'],
                    'restaurant': ['restaurant', 'cafe', 'dining', 'eatery'],
                    'beach': ['beach', 'ocean', 'sea', 'shore', 'sand'],
                    'mountain': ['mountain', 'hill', 'peak', 'summit'],
                    'road': ['road', 'highway', 'street', 'path']
                }
                
                detected_object = None
                for obj, obj_variants in object_keywords.items():
                    for variant in obj_variants:
                        # Word boundary check - be strict for object matching
                        if f' {variant} ' in f' {query_lower} ' or query_lower.startswith(variant + ' ') or query_lower.endswith(' ' + variant) or query_lower == variant:
                            detected_object = obj
                            print(f"👁️ Detected object filter: '{obj}' - will validate this object is visible!")
                            break
                    if detected_object:
                        break
                
                if detected_object:
                    desc_lower = description.lower() if description else ''
                    people_desc_lower = people_description.lower() if people_description else ''
                    env_lower = environment.lower() if environment else ''
                    tags_combined = f"{tags} {contextual_tags} {character_tags} {semantic_tags}".lower()
                    
                    # Combine all visual fields for validation
                    visual_content = f"{desc_lower} {people_desc_lower} {env_lower} {tags_combined}"
                    
                    object_valid = False
                    object_check_variants = object_keywords[detected_object]
                    
                    # Check if ANY variant of the object appears in visual descriptions
                    for variant in object_check_variants:
                        if variant in visual_content:
                            object_valid = True
                            break
                    
                    # IMPORTANT: Only filter if we have good description data
                    # If description is too short/empty, don't filter (Vision API might have failed)
                    has_good_data = len(visual_content) > 50 and desc_lower != 'video frame'
                    
                    # Skip if object is not present AND we have good data to validate against
                    if not object_valid and has_good_data:
                        print(f"   ⚠️ Skipping result - '{detected_object}' not found in video (searched for but not visible)")
                        continue  # Skip to next result
                    elif not object_valid and not has_good_data:
                        print(f"   ⚠️ '{detected_object}' not found, but description is incomplete - including result anyway")
                        # Allow result through since we can't reliably validate
                
                # EMOTION CONTRADICTION CHECKING: Prevent opposite emotions
                emotion_contradictions = {
                    'happy': ['sad', 'sorrow', 'melancholy', 'grief', 'crying', 'tears', 'depressed', 'unhappy'],
                    'sad': ['happy', 'joy', 'joyful', 'cheerful', 'laughing', 'celebrating', 'excited'],
                    'angry': ['calm', 'peaceful', 'happy', 'joyful', 'content', 'relaxed'],
                    'calm': ['angry', 'rage', 'furious', 'chaotic', 'wild', 'frantic', 'agitated'],
                    'excited': ['bored', 'tired', 'exhausted', 'lethargic', 'sleepy', 'calm', 'peaceful'],
                    'scared': ['confident', 'brave', 'fearless', 'bold', 'courageous'],
                    'confident': ['nervous', 'anxious', 'scared', 'fearful', 'worried', 'uncertain']
                }
                
                # Check if query contains an emotion keyword
                for emotion_keyword, opposite_emotions in emotion_contradictions.items():
                    if emotion_keyword in query_lower.split():
                        # Check if the video has opposite emotions
                        video_emotions = f"{emotion} {deep_emotions} {emotion_tags}".lower()
                        
                        has_opposite = any(opposite in video_emotions for opposite in opposite_emotions)
                        
                        if has_opposite:
                            # Double-check: only skip if the desired emotion is NOT present
                            has_desired = emotion_keyword in video_emotions
                            if not has_desired:
                                continue  # Skip this result - it has opposite emotion
                        
                        break
                
                # SEMANTIC THRESHOLD: 30% for visual (lower than audio for better semantic matching)
                # Visual descriptions + tags provide richer semantic context
                min_threshold = 0.30
                
                if boosted_similarity > min_threshold:
                    # Build display text with emotion and OCR
                    display_text = f"[Visual] {description}"
                    if emotion and emotion != 'neutral':
                        display_text = f"[Visual - {emotion.title()}] {description}"
                    if ocr_text:
                        display_text += f" | Text: \"{ocr_text}\""
                    
                    results.append({
                        'id': f"visual_{frame_id}",
                        'video_id': video_id,
                        'filename': filename,
                        'timestamp': timestamp,
                        'start_time': timestamp,
                        'end_time': timestamp + 10,  # Show 10s window
                        'duration': 10.0,
                        'text': display_text,
                        'similarity': float(boosted_similarity),  # Use boosted score
                        'source': 'visual',
                        'emotion': emotion or 'neutral',
                        'ocr_text': ocr_text or '',
                        'tags': tags or '',
                        'genres': genres or '',
                        'custom_tags': custom_tags or '',
                        'emotion_tags': emotion_tags or '',
                        'laugh_tags': laugh_tags or '',
                        'contextual_tags': contextual_tags or '',
                        'character_tags': character_tags or '',
                        'semantic_tags': semantic_tags or ''
                    })
        
        conn.close()
        
        # Apply filters AFTER semantic search (as requested)
        if emotions_filter or genres_filter:
            filtered_results = []
            for result in results:
                # Check emotion filter
                emotion_match = True
                if emotions_filter:
                    result_emotion = result.get('emotion', 'neutral').lower()
                    emotion_match = result_emotion in [e.lower() for e in emotions_filter]
                
                # Check genre filter
                genre_match = True
                if genres_filter and result.get('source') == 'visual':
                    result_genres = result.get('genres', '').lower().split(', ')
                    genre_match = any(g.lower() in result_genres for g in genres_filter)
                elif genres_filter and result.get('source') == 'audio':
                    # For audio-only results, skip genre filtering (no visual genres)
                    genre_match = False
                
                # Include result if it matches all active filters
                if emotion_match and genre_match:
                    filtered_results.append(result)
            
            results = filtered_results
            print(f"🔍 Applied filters: {len(filtered_results)} results after filtering")
        
        # Sort by similarity (descending) - combines audio and visual results
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Count results by source
        audio_count = sum(1 for r in results if r['source'] == 'audio')
        visual_count = sum(1 for r in results if r['source'] == 'visual')
        
        print(f"✅ Found {len(results)} total matches:")
        print(f"   🎤 Audio: {audio_count} clips")
        print(f"   🎨 Visual: {visual_count} frames")
        if results:
            print(f"   🏆 Top match ({results[0]['source']}): {results[0]['similarity']:.2%}")
        
        # If no relevant results found, return empty with message
        if len(results) == 0:
            print(f"⚠️  No relevant results found for '{query}' (all below relevance threshold)")
            
            # Provide specific message if series was detected but no results found
            if detected_series:
                return jsonify({
                    'results': [],
                    'message': f'No B-rolls found from "{detected_series}". Either: (1) You don\'t have videos from this movie/series, or (2) The AI didn\'t detect the movie name in your videos. Try clicking "Add Visual" to reprocess videos from this movie.'
                })
            else:
                return jsonify({
                    'results': [],
                    'message': f'No relevant B-rolls found for "{query}". Try different keywords or upload more videos.'
                })
        
        # Return top 20 results (mixed audio + visual)
        return jsonify({'results': results[:20]})
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Search error:\n{error_detail}")
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_video(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAILS_FOLDER, filename)

@app.route('/videos', methods=['GET'])
def list_videos():
    """List all uploaded videos with their status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.id, v.filename, v.upload_date, v.duration, v.status, v.thumbnail, v.custom_tags, COUNT(c.id) as clip_count
            FROM videos v
            LEFT JOIN clips c ON v.id = c.video_id
            GROUP BY v.id
            ORDER BY v.upload_date DESC
        ''')
        
        videos = []
        for row in cursor.fetchall():
            video_id, filename, upload_date, duration, status, thumbnail, custom_tags, clip_count = row
            videos.append({
                'id': video_id,
                'filename': filename,
                'upload_date': upload_date,
                'duration': duration,
                'status': status,
                'thumbnail': thumbnail,
                'custom_tags': custom_tags or '',
                'clip_count': clip_count
            })
        
        conn.close()
        return jsonify({'videos': videos})
    except Exception as e:
        print(f"❌ Error listing videos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reprocess/<int:video_id>', methods=['POST'])
def reprocess_video(video_id):
    """Re-process a video to add visual analysis."""
    print(f"\n{'='*60}")
    print(f"🔄 RE-PROCESS REQUEST - Video ID: {video_id}")
    print(f"{'='*60}")
    
    conn = None
    try:
        # Get video info first, then close connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT filename, duration FROM videos WHERE id = ?', (video_id,))
        video_data = cursor.fetchone()
        
        if not video_data:
            conn.close()
            return jsonify({'error': 'Video not found'}), 404
        
        filename, video_duration = video_data
        
        # Check existing frames
        cursor.execute('SELECT COUNT(*) FROM visual_frames WHERE video_id = ?', (video_id,))
        existing_frames = cursor.fetchone()[0]
        
        if existing_frames > 0:
            print(f"⚠️  Video already has {existing_frames} visual frames - DELETING OLD FRAMES")
            cursor.execute('DELETE FROM visual_frames WHERE video_id = ?', (video_id,))
            conn.commit()
            print(f"   ✅ Old visual frames deleted")
        
        # Close connection before long operation
        conn.close()
        conn = None
        
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(video_path):
            return jsonify({'error': 'Video file not found'}), 404
        
        print(f"📁 Re-processing: {filename}")
        print(f"📹 Video duration: {video_duration}s")
        
        # Extract and analyze frames (without DB connection open)
        print(f"\n🎨 Starting visual analysis...")
        try:
            frames = extract_frames_for_analysis(video_path, video_duration, filename)
            if not frames or len(frames) == 0:
                print(f"❌ No frames could be extracted from video")
                return jsonify({'error': 'Failed to extract frames from video. Video may be corrupted.'}), 500
            print(f"✅ Extracted {len(frames)} frames for analysis")
        except Exception as extract_error:
            print(f"❌ Frame extraction error: {str(extract_error)}")
            return jsonify({'error': f'Failed to extract frames: {str(extract_error)}'}), 500
        
        # Re-open connection for storing results
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # GET TRANSCRIPT FOR THIS VIDEO (for context-rich visual descriptions)
        cursor.execute('SELECT transcript_text FROM clips WHERE video_id = ? ORDER BY start_time', (video_id,))
        transcript_rows = cursor.fetchall()
        full_transcript = ' '.join([row[0] for row in transcript_rows if row[0]]) if transcript_rows else ''
        print(f"📝 Transcript loaded: {len(full_transcript)} characters")
        
        visual_count = 0
        failed_frames = 0
        for frame_data in frames:
            try:
                print(f"  🔍 Analyzing frame at {frame_data['timestamp']}s...")
                
                # Get transcript segment near this timestamp (±10s window)
                cursor.execute('''
                    SELECT transcript_text FROM clips 
                    WHERE video_id = ? 
                    AND start_time <= ? 
                    AND end_time >= ?
                    ORDER BY start_time
                    LIMIT 3
                ''', (video_id, frame_data['timestamp'] + 10, frame_data['timestamp'] - 10))
                
                nearby_transcripts = cursor.fetchall()
                context_transcript = ' '.join([row[0] for row in nearby_transcripts if row[0]])
                
                # Analyze frame with Vision API + transcript context + filename hint
                analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context_transcript, filename_hint=filename)
                
                # Check if analysis was successful
                if not analysis:
                    print(f"     ⚠️  Frame analysis returned None - skipping this frame")
                    failed_frames += 1
                    continue
                    
            except Exception as frame_error:
                print(f"     ⚠️  Frame analysis failed: {str(frame_error)}")
                print(f"     Skipping frame at {frame_data['timestamp']}s and continuing...")
                failed_frames += 1
                continue  # Skip this frame and continue with next one
            
            if analysis:
                # Extract ALL metadata from analysis with SAFE TYPE CONVERSION
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
                
                # Extract CATEGORIZED TAGS (5 categories) - Convert arrays to comma-separated strings
                def parse_tag_array(tag_data):
                    """Convert tag array/list to comma-separated string"""
                    if isinstance(tag_data, list):
                        return ', '.join(str(tag) for tag in tag_data if tag)
                    elif isinstance(tag_data, str):
                        return tag_data
                    else:
                        return str(tag_data) if tag_data else ''
                
                emotion_tags = parse_tag_array(analysis.get('emotion_tags', ''))
                laugh_tags = parse_tag_array(analysis.get('laugh_tags', ''))
                contextual_tags = parse_tag_array(analysis.get('contextual_tags', ''))
                character_tags = parse_tag_array(analysis.get('character_tags', ''))
                semantic_tags = parse_tag_array(analysis.get('semantic_tags', ''))
                
                # FALLBACK: If Vision API didn't return categorized tags, INTELLIGENTLY GENERATE them
                if not emotion_tags and not laugh_tags and not contextual_tags:
                    print(f"     ⚠️  Vision API didn't return categorized tags - intelligently generating from analysis...")
                    generated = intelligently_generate_categorized_tags(analysis)
                    emotion_tags = generated['emotion_tags']
                    laugh_tags = generated['laugh_tags']
                    contextual_tags = generated['contextual_tags']
                    character_tags = generated['character_tags']
                    semantic_tags = generated['semantic_tags']
                    print(f"     ✅ Generated {generated['total_count']} tags: Emotion={generated['counts']['emotion']}, Laugh={generated['counts']['laugh']}, Context={generated['counts']['contextual']}, Char={generated['counts']['character']}, Semantic={generated['counts']['semantic']}")
                
                
                print(f"     📝 Description: {description[:80]}...")
                if actors:
                    print(f"     🎭 Actors: {actors}")
                
                # Extract clean title from filename for metadata
                clean_title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
                
                # Create COMPREHENSIVE embedding text with ALL metadata including categorized tags
                combined_text = f"Title: {clean_title}. {description}. Emotion: {emotion}."
                if deep_emotions:
                    combined_text += f" Deep Emotions: {deep_emotions}."
                if scene_context:
                    combined_text += f" Scene: {scene_context}."
                if people_description:
                    combined_text += f" People: {people_description}."
                if environment:
                    combined_text += f" Environment: {environment}."
                if dialogue_context:
                    combined_text += f" Dialogue: {dialogue_context}."
                if series_movie:
                    combined_text += f" Series/Movie: {series_movie}."
                if ocr_text:
                    combined_text += f" Text on screen: {ocr_text}."
                if tags:
                    combined_text += f" Tags: {tags}."
                if emotion_tags:
                    combined_text += f" Emotion Tags: {emotion_tags}."
                if laugh_tags:
                    combined_text += f" Laugh Tags: {laugh_tags}."
                if contextual_tags:
                    combined_text += f" Context: {contextual_tags}."
                if character_tags:
                    combined_text += f" Characters: {character_tags}."
                if semantic_tags:
                    combined_text += f" Semantic: {semantic_tags}."
                if genres:
                    combined_text += f" Genres: {genres}."
                
                # Create embedding from comprehensive metadata
                print(f"     🧠 Creating visual embedding with comprehensive metadata...")
                visual_embedding = create_embedding(combined_text)
                
                # Store visual data with ALL fields (basic + advanced tagging + categorized tags)
                cursor.execute('''
                    INSERT INTO visual_frames (
                        video_id, filename, timestamp, frame_path, visual_description, visual_embedding, 
                        emotion, ocr_text, tags, genres,
                        deep_emotions, scene_context, people_description, environment, 
                        dialogue_context, series_movie, target_audience, scene_type, actors, media_type,
                        emotion_tags, laugh_tags, contextual_tags, character_tags, semantic_tags
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video_id,
                    filename,
                    frame_data['timestamp'],
                    frame_data['filename'],
                    description,
                    visual_embedding,
                    emotion,
                    ocr_text,
                    tags,
                    genres,
                    deep_emotions,
                    scene_context,
                    people_description,
                    environment,
                    dialogue_context,
                    series_movie,
                    target_audience,
                    scene_type,
                    actors,
                    media_type,
                    emotion_tags,
                    laugh_tags,
                    contextual_tags,
                    character_tags,
                    semantic_tags
                ))
                visual_count += 1
                print(f"     ✅ Visual data stored")
        
        conn.commit()
        conn.close()
        conn = None
        
        if visual_count == 0:
            print(f"\n❌ Re-processing failed: No frames were successfully analyzed")
            if failed_frames > 0:
                print(f"   {failed_frames} frames failed during analysis")
            return jsonify({'error': 'No frames could be analyzed. Please check OpenAI API key and try again.'}), 500
        
        print(f"\n✅ Re-processing complete: {visual_count} visual frames added")
        if failed_frames > 0:
            print(f"   ⚠️  {failed_frames} frames failed but processing continued")
        return jsonify({'success': True, 'visual_frames_added': visual_count, 'failed_frames': failed_frames})
        
    except sqlite3.OperationalError as e:
        error_msg = str(e)
        print(f"❌ Database error: {error_msg}")
        if conn:
            try:
                conn.close()
            except:
                pass
        return jsonify({'error': f'Database error: {error_msg}'}), 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Re-process error:\n{error_detail}")
        if conn:
            try:
                conn.close()
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/filters', methods=['GET'])
def get_filters():
    """Get available emotions and genres for filtering."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all unique emotions
        cursor.execute('SELECT DISTINCT emotion FROM visual_frames WHERE emotion IS NOT NULL AND emotion != ""')
        emotions = sorted([row[0] for row in cursor.fetchall()])
        
        # Get all unique genres (split comma-separated values)
        cursor.execute('SELECT genres FROM visual_frames WHERE genres IS NOT NULL AND genres != ""')
        all_genres = set()
        for row in cursor.fetchall():
            genres_str = row[0]
            if genres_str:
                for genre in genres_str.split(', '):
                    all_genres.add(genre.strip())
        
        genres = sorted(list(all_genres))
        
        conn.close()
        
        return jsonify({
            'emotions': emotions,
            'genres': genres
        })
    except Exception as e:
        print(f"❌ Error fetching filters: {e}")
        return jsonify({'emotions': [], 'genres': []})

@app.route('/videos/<int:video_id>/tags', methods=['POST'])
def add_custom_tag(video_id):
    """Add a custom tag to a video."""
    print(f"\n{'='*60}")
    print(f"🏷️  ADD CUSTOM TAG - Video ID: {video_id}")
    print(f"{'='*60}")
    
    try:
        data = request.json
        new_tag = data.get('tag', '').strip()
        
        if not new_tag:
            return jsonify({'error': 'Tag cannot be empty'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current custom tags
        cursor.execute('SELECT custom_tags FROM videos WHERE id = ?', (video_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Video not found'}), 404
        
        current_tags = row[0] or ''
        
        # Parse existing tags
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip()]
        
        # Check if tag already exists (case-insensitive)
        if new_tag.lower() in [t.lower() for t in tags_list]:
            conn.close()
            return jsonify({'error': 'Tag already exists', 'tags': ', '.join(tags_list)}), 400
        
        # Add new tag
        tags_list.append(new_tag)
        updated_tags = ', '.join(tags_list)
        
        # Update database
        cursor.execute('UPDATE videos SET custom_tags = ? WHERE id = ?', (updated_tags, video_id))
        conn.commit()
        conn.close()
        
        print(f"✅ Tag '{new_tag}' added to video {video_id}")
        print(f"   All tags: {updated_tags}")
        
        return jsonify({
            'success': True,
            'tag': new_tag,
            'all_tags': updated_tags
        })
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Add tag error:\n{error_detail}")
        return jsonify({'error': str(e)}), 500

@app.route('/videos/<int:video_id>/tags/<path:tag>', methods=['DELETE'])
def delete_custom_tag(video_id, tag):
    """Delete a custom tag from a video."""
    print(f"\n{'='*60}")
    print(f"🗑️  DELETE CUSTOM TAG - Video ID: {video_id}, Tag: {tag}")
    print(f"{'='*60}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current custom tags
        cursor.execute('SELECT custom_tags FROM videos WHERE id = ?', (video_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Video not found'}), 404
        
        current_tags = row[0] or ''
        
        # Parse existing tags
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip()]
        
        # Remove tag (case-insensitive match)
        tags_list = [t for t in tags_list if t.lower() != tag.lower()]
        
        updated_tags = ', '.join(tags_list)
        
        # Update database
        cursor.execute('UPDATE videos SET custom_tags = ? WHERE id = ?', (updated_tags, video_id))
        conn.commit()
        conn.close()
        
        print(f"✅ Tag '{tag}' removed from video {video_id}")
        print(f"   Remaining tags: {updated_tags}")
        
        return jsonify({
            'success': True,
            'deleted_tag': tag,
            'remaining_tags': updated_tags
        })
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Delete tag error:\n{error_detail}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete a video and all its associated data."""
    print(f"\n{'='*60}")
    print(f"🗑️  DELETE REQUEST - Video ID: {video_id}")
    print(f"{'='*60}")
    
    conn = None
    try:
        # Use longer timeout to avoid database locked errors
        conn = sqlite3.connect(DATABASE, timeout=30.0, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
        cursor = conn.cursor()
        
        # Get video info before deleting
        cursor.execute('SELECT filename, thumbnail FROM videos WHERE id = ?', (video_id,))
        video_data = cursor.fetchone()
        
        if not video_data:
            if conn:
                conn.close()
            return jsonify({'error': 'Video not found'}), 404
        
        filename, thumbnail = video_data
        print(f"📁 Deleting: {filename}")
        
        # Delete from database with immediate commit for each operation
        cursor.execute('DELETE FROM clips WHERE video_id = ?', (video_id,))
        conn.commit()
        print(f"   ✅ Deleted audio clips")
        
        cursor.execute('DELETE FROM visual_frames WHERE video_id = ?', (video_id,))
        conn.commit()
        print(f"   ✅ Deleted visual frames")
        
        cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
        conn.commit()
        print(f"   ✅ Deleted video record")
        
        conn.close()
        conn = None
        
        # Delete files
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"✅ Deleted video file: {video_path}")
        
        if thumbnail:
            thumbnail_path = os.path.join(THUMBNAILS_FOLDER, thumbnail)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                print(f"✅ Deleted thumbnail: {thumbnail_path}")
        
        # Delete frame files
        video_base = os.path.splitext(filename)[0]
        for frame_file in os.listdir(FRAMES_FOLDER):
            if frame_file.startswith(f"{video_base}_frame_"):
                frame_path = os.path.join(FRAMES_FOLDER, frame_file)
                os.remove(frame_path)
                print(f"✅ Deleted frame: {frame_file}")
        
        print(f"✅ Video and all associated data deleted successfully")
        return jsonify({'success': True})
        
    except Exception as e:
        if conn:
            try:
                conn.close()
            except:
                pass
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Delete error:\n{error_detail}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 B-ROLL MULTI-MODAL SEARCH - STARTING UP")
    print("="*60)
    print("✅ OpenAI Whisper API - Audio Transcription")
    print("✅ OpenAI Vision API - Visual Analysis")
    print("✅ OpenAI Embeddings API - Multi-Modal Search")
    print("✅ SQLite Database - Vector Storage")
    print("✅ Server: http://localhost:5002")
    print("="*60 + "\n")
    app.run(debug=False, port=5002)
