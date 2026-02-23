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
from PIL import Image

# Import Gemini analyzer
from gemini_analyzer import analyze_frame_with_gemini

# Load environment variables
load_dotenv()

# Check Gemini API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY and GEMINI_API_KEY != 'YOUR_GEMINI_API_KEY_HERE':
    print("✅ Gemini API key loaded for visual analysis")
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
        
        # IMPROVED FRAME EXTRACTION: More frames for better context
        # Videos under 20s: 1 frame at middle
        # Videos 20-60s: 2 frames (at 1/3 and 2/3)
        # Videos over 60s: 3 frames (at 25%, 50%, 75%)
        if video_duration <= 20:
            # Very short: 1 frame at middle
            timestamps = [video_duration / 2]
            print(f"🎞️  Extracting 1 frame (SHORT VIDEO - at middle)")
        elif video_duration <= 60:
            # Medium: 2 frames for better context
            timestamps = [video_duration / 3, video_duration * 2 / 3]
            print(f"🎞️  Extracting 2 frames (MEDIUM VIDEO - at 1/3 and 2/3)")
        else:
            # Long: 3 frames for comprehensive coverage
            timestamps = [video_duration * 0.25, video_duration * 0.5, video_duration * 0.75]
            print(f"🎞️  Extracting 3 frames (LONG VIDEO - at 25%, 50%, 75%)")
        
        for timestamp in timestamps:
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
    Analyze frame using OpenAI Vision API with Pro-Level B-Roll Asset Manager Prompt.
    Optimized for speed and accuracy.
    """
    try:
        # Read and encode image
        with open(frame_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Build context
        context_info = ""
        if transcript_context:
            context_info += f"\n\nDialogue/Transcript: {transcript_context}\n"
        if filename_hint:
            clean_hint = filename_hint.replace('_', ' ').replace('-', ' ').replace('.mp4', '').replace('.gif', '').replace('.mov', '')
            context_info += f"\nFilename Hint (may contain movie name): {clean_hint}\n"
        
        # PRO-LEVEL B-ROLL METADATA PROMPT (User's exact prompt - OPENAI OPTIMIZED)
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

STEP-BY-STEP ANALYSIS:

1. LOOK CAREFULLY AT THE PEOPLE:
   - How many people? (1, 2, 3+)
   - Gender? (male, female, mix)
   - Ages? (child, young adult, middle-aged, elderly)
   - What are they DOING? (hugging, crying, laughing, sitting, standing, talking, fighting)
   - Facial expressions? (tears visible, smiling, angry, neutral)
   
2. LOOK FOR CONTEXT CLUES:
   - Setting: home/office/warehouse/street/outdoor?
   - Objects: money, car, phone, food, weapons?
   - Clothing: casual, formal, traditional, uniform?
   - Lighting: bright, dim, natural, indoor, outdoor?

3. UNDERSTAND THE RELATIONSHIP & SCENE TYPE:
   - Age difference + home + crying = FAMILY (father-son, mother-daughter)
   - Money piles + laughing + warehouse = CRIME/HEIST
   - Office + serious = WORKPLACE
   - Friends hanging out = FRIENDSHIP
   
4. IDENTIFY MOVIE/SERIES & CHARACTERS:
   **STEP 1: READ THE FILENAME FIRST! (Most Important)**
     - "Aamir_Khan" or "Aamir Khan" in filename → 3 IDIOTS (Aamir Khan as Rancho)
     - "Kamyab_Nahi_Kabil" in filename → 3 IDIOTS movie (famous dialogue scene)
     - "Farzi" in filename → FARZI series (Sunny/Shahid Kapoor, Firoz/Bhuvan Arora)
     - "3_Idiots" or "3 Idiots" in filename → 3 IDIOTS movie
     - "Scam_1992" or "Scam 1992" in filename → SCAM 1992 series
     - "Shahid_Kapoor" in filename → Likely FARZI (Shahid plays Sunny)
     - "R_Madhavan" or "Madhavan" in filename → Likely 3 IDIOTS (Madhavan plays Farhan)
     - "Highway" in filename → HIGHWAY movie
   **STEP 2: Check transcript** for character/actor names mentioned in dialogue
   **STEP 3: Visual recognition** - recognize famous actors if visible
   **MANDATORY: Extract character names from filename and USE them in tags!**

GENERATE DETAILED TAGS:

Visual Description (2-3 detailed sentences):
- Sentence 1: WHO (use names from filename/transcript) + WHAT specific action + WHERE
- Sentence 2: Details about facial expressions, emotions visible, body language
- Sentence 3: Camera angle, lighting, setting atmosphere
- BE SPECIFIC: "Aamir Khan as Rancho teaches students in a classroom" NOT "man talking"
- INCLUDE VISIBLE ACTIONS: hugging, crying, laughing, shaving, sitting, standing
- DESCRIBE EMOTIONS: tears streaming, smiling widely, serious expression, distressed
- Example 1: "Aamir Khan as Rancho stands at the front of a classroom teaching students about success, gesturing expressively with passion in his eyes. The setting is a college lecture hall with students visible in the background. Warm indoor lighting creates an inspirational atmosphere."
- Example 2: "An elderly man and young man embrace tightly in a dimly lit home, both with tears streaming down their faces showing profound grief. The father buries his face in his son's shoulder while the son holds him protectively. Soft warm lighting emphasizes the intimate emotional moment."
- Example 3: "Two men sit atop a massive pile of bundled cash in an industrial warehouse, throwing their heads back in manic laughter with wide open-mouthed grins. They're wearing casual colorful shirts and sunglasses, surrounded by concrete walls. The dim overhead lighting creates a gritty underground atmosphere."

Scene Summary (2-3 sentences):
- Explain what's happening emotionally/narratively
- Why is this moment significant?

Series/Movie: Name if you recognize it

Characters: Names if you know them from context, otherwise describe (e.g., "father and son", "two male friends")

Basic Emotion: sad/happy/laughing/crying/angry/surprised/fear/love/neutral

Emotion Tags (20-30 specific emotions):
- FAMILY CRYING: paternal-grief, unbearable-loss, heartbroken, anguish, father-son-pain, reconciliation-tears, forgiveness, healing-tears, vulnerable-moment, raw-emotion, emotional-reunion, family-sorrow, deep-sadness, overwhelming-grief, cathartic-release
- CRIME LAUGHING: euphoric, financial-rebellion, power-high, money-intoxication, rebellious, disbelief, triumphant, mad-joy, wild-success, moral-decay, criminal-euphoria, reckless-confidence, adrenaline-rush
- HAPPY/JOY: contentment, satisfaction, relief, peace, fulfillment, pride, gratitude, hope, warmth, affection

Laugh Tags (CRITICAL - if ANY smiling/laughing - 10-15 types):
- **MANDATORY: If you see smiling, grinning, or laughing → Generate laugh tags!**
- **OFFICE/PROFESSIONAL with smile:** friendly-laugh, professional-laugh, warm-laugh, happy-laugh, genuine-laugh, pleasant-laugh, comfortable-laugh, conversational-laugh, positive-laugh, engaging-laugh
- **CRIME/HEIST laughing:** criminal-success-laugh, maniacal-laugh, evil-laugh, unhinged-joy, illegal-jackpot-laugh, boys-gone-rogue-laugh, delirious-laugh, manic-glee, dark-comedy-laugh, robbery-laugh
- **FAMILY/JOY laughing:** genuine-joy-laugh, heartfelt-laugh, relief-laugh, warm-laugh, happy-laugh, gentle-laugh, family-laugh, tender-laugh
- **If ONLY smiling (not laughing):** warm-smile, happy-smile, content-smile, friendly-smile, pleasant-smile, engaging-smile
- **If NO smiling or laughing visible:** empty array []

Contextual Tags (20-30 scene context + COMMON SEARCHABLE TAGS):
- **FAMILY:** family-drama, emotional-reunion, forgiveness-journey, father-son-relationship, mother-daughter, home-scene, reconciliation, healing-moment, intimate-moment, family-bond, parent-child-moment, family-hug, family-embrace, emotional-family-scene
- **CRIME:** crime-comedy, heist-aftermath, underground-lair, fake-money-aesthetic, counterfeit-operation, criminal-success, illegal-victory, robbery-celebration, financial-crime, money-scene, cash-scene, heist-scene
- **OFFICE/WORK:** office-setting, professional-atmosphere, workplace-scene, business-call, phone-conversation, work-discussion, corporate-scene, professional-interaction, office-communication
- **Plus lighting/setting:** warm-lighting, bright-lighting, dim-lighting, indoor-scene, outdoor-scene, natural-light, professional-setting, home-setting, industrial-setting
- **Plus common search terms:** talking, phone-call, conversation, discussion, hug, embrace, sitting, standing, laughing, smiling, crying, tears, emotional-moment

Character Tags (15-25 tags - BE COMPREHENSIVE):
- **MANDATORY: Extract names from filename!**
  - If "Aamir_Khan" in filename: Aamir-Khan, Rancho, 3-Idiots, Rancho-3-Idiots, Aamir-Khan-as-Rancho, professor-Rancho, teacher-character
  - If "Shahid_Kapoor" in filename: Shahid-Kapoor, Sunny, Farzi, Sunny-Farzi, Shahid-Kapoor-as-Sunny
  - If "R_Madhavan" in filename: R-Madhavan, Farhan, 3-Idiots, Farhan-3-Idiots, R-Madhavan-as-Farhan
- **Include relationships:** father-son, duo, partners, friends, bromance, criminal-duo, family-members
- **Include roles:** teacher, student, professor, father, son, criminal, friend, mentor, leader
- **Include movie context:** 3-Idiots-character, Farzi-character, main-protagonist, supporting-character
- **Example for Aamir Khan teaching scene:** Aamir-Khan, Rancho, 3-Idiots, Rancho-3-Idiots, Aamir-Khan-as-Rancho, teacher, professor, mentor, inspirational-figure, main-protagonist, college-professor, motivational-speaker, educational-leader, wisdom-giver
- **Example for father-son hug:** father, son, father-son, parent-child, paternal-figure, family-member, male-relatives, elderly-man, young-man, Farhan (if 3 Idiots), R-Madhavan (if recognized)

Semantic Tags (25-40 visible details - DESCRIBE EVERYTHING):
- **People:** facial-expressions, body-language, gestures, posture, eye-contact, tears, smiling, crying, laughing
- **Actions:** hugging, embracing, sitting, standing, walking, talking, teaching, gesturing, pointing, shaving, mirror, looking
- **Clothing:** casual-attire, formal-suit, traditional-clothing, patterned-shirt, colorful-shirt, sunglasses, glasses, traditional-wear, western-wear
- **Setting:** home-interior, office-space, classroom, warehouse, street, outdoor, indoor, bathroom, bedroom, living-room
- **Objects:** money, cash-bundles, stacks-of-cash, counterfeit-bills, phone, laptop, car, mirror, shaving-cream, towel, furniture, curtains, walls
- **Lighting:** warm-lighting, soft-lighting, dim-lighting, bright-lighting, natural-light, overhead-lighting, mood-lighting
- **Atmosphere:** intimate-moment, emotional-atmosphere, warm-atmosphere, cold-industrial, underground-feel, cozy-home, professional-setting
- **Camera:** close-up, wide-shot, medium-shot, over-shoulder, eye-level, low-angle
- **Example for crying scene:** tears, crying, hug, embrace, tight-embrace, emotional-hug, home-interior, soft-lighting, warm-atmosphere, traditional-clothing, facial-expressions, tearful-eyes, body-language, physical-contact, close-proximity, curtains, family-photos, wooden-furniture, dim-lighting, intimate-moment, close-up-shot
- **Example for money scene:** stacks-of-cash, counterfeit-bills, money-pile, bundles-of-cash, 500-rupee-notes, industrial-warehouse, concrete-walls, dim-lighting, patterned-shirts, colorful-shirts, designer-sunglasses, casual-attire, urban-background, underground-setting, wide-shot, low-angle, gritty-atmosphere

Return ONLY valid JSON:

{{
  "visual_description": "2-3 detailed sentences: WHO (use names from filename!) + WHAT action + WHERE + facial expressions + body language + camera/lighting",
  "scene_summary": "2-3 sentences about emotional/narrative significance and why this moment matters",
  "series_movie": "EXACT movie/series name from filename (e.g., '3 Idiots', 'Farzi', 'Scam 1992')",
  "characters": "Character names from filename/transcript (e.g., 'Aamir Khan as Rancho', 'Sunny (Shahid Kapoor)')",
  "basic_emotion": "sad/happy/laughing/crying/angry/surprised/fear/love/neutral",
  "emotion_tags": ["20-30 specific emotion tags based on scene type - context-aware"],
  "laugh_tags": ["10-15 laugh types if laughing (criminal-laugh/evil-laugh for crime, genuine-laugh for family), empty [] if not"],
  "contextual_tags": ["20-30 scene context: genre, setting, mood, relationships, scene-type, movie-context"],
  "character_tags": ["15-25 COMPREHENSIVE tags: actor names from filename, character names, relationships, roles, movie-character tags"],
  "semantic_tags": ["25-40 visible details: actions, clothing, objects, setting, lighting, atmosphere, camera angle, facial expressions"]
}}

FINAL CHECKLIST BEFORE RETURNING JSON:
✅ Did you READ THE FILENAME and extract character/actor names?
✅ Did you identify the movie/series from filename clues?
✅ Did you include character names in character_tags? (NOT "two-young-men"!)
✅ Did you describe the specific ACTION visible? (hugging, crying, laughing, teaching)
✅ Did you generate 20-30 emotion tags based on context?
✅ Did you generate 15-25 character tags including names from filename?
✅ Did you generate 25-40 semantic tags describing everything visible?
✅ Total tags should be 100-150+ for comprehensive searchability

Return ONLY JSON, no other text."""

        # Call OpenAI Vision API (optimized for speed and quality)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}", "detail": "low"}}  # Low detail for speed
                    ]
                }
            ],
            max_tokens=3000,  # Increased for 50-100+ tags
            temperature=0.3  # Lower temperature for more consistent/accurate outputs
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Clean JSON
        if result_text.startswith('```'):
            lines = result_text.split('\n')[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            result_text = '\n'.join(lines).strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        result = json.loads(result_text)
        
        # Convert to database format
        emotion_tags_list = result.get('emotion_tags', [])
        laugh_tags_list = result.get('laugh_tags', [])
        contextual_tags_list = result.get('contextual_tags', [])
        character_tags_list = result.get('character_tags', [])
        semantic_tags_list = result.get('semantic_tags', [])
        
        # Get basic emotion label
        basic_emotion = result.get('basic_emotion', 'neutral')
        
        # Calculate total tags
        total_tags = len(emotion_tags_list) + len(laugh_tags_list) + len(contextual_tags_list) + len(character_tags_list) + len(semantic_tags_list)
        
        all_tags = character_tags_list + semantic_tags_list
        
        # Extract actor/character names
        characters_str = result.get('characters', '')
        actor_name = ''
        if '(' in characters_str and ')' in characters_str:
            # Format: "Character Name (Actor Name)"
            actor_name = characters_str.split('(')[1].split(')')[0].strip()
        elif ' as ' in characters_str:
            # Format: "Actor as Character"
            actor_name = characters_str.split(' as ')[0].strip()
        elif characters_str and characters_str not in ['Unknown', 'Unknown — Unknown Film']:
            parts = characters_str.split()
            if len(parts) >= 2:
                actor_name = ' '.join(parts[:2])
        
        # Build clean, readable description
        visual_desc = result.get('visual_description', '')
        scene_summary = result.get('scene_summary', '')
        
        # Use basic emotion as primary label (easier to understand)
        # Format: [Visual - Basic Emotion] Visual description. Scene summary.
        full_description = f"[Visual - {basic_emotion.title()}] {visual_desc} {scene_summary}".strip()
        
        print(f"     ✅ TOTAL TAGS: {total_tags} ({len(emotion_tags_list)} emotion, {len(laugh_tags_list)} laugh, {len(contextual_tags_list)} contextual, {len(character_tags_list)} character, {len(semantic_tags_list)} semantic)")
        print(f"     🎬 Movie: {result.get('series_movie', 'Unknown')}")
        print(f"     😊 Basic Emotion: {basic_emotion}")
        print(f"     👁️  Visual: {visual_desc[:70]}...")
        
        return {
            'description': full_description,
            'emotion': basic_emotion,  # Use basic emotion as primary
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
        import traceback
        traceback.print_exc()
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
                
                # ACTOR NAME FILTERING: If query is an actor name, ONLY show videos with that actor
                known_actors = {
                    'ranbir': ['ranbir kapoor', 'ranbir'],
                    'ranbir kapoor': ['ranbir kapoor', 'ranbir'],
                    'shahid': ['shahid kapoor', 'shahid'],
                    'shahid kapoor': ['shahid kapoor', 'shahid'],
                    'aamir': ['aamir khan', 'aamir'],
                    'aamir khan': ['aamir khan', 'aamir'],
                    'shahrukh': ['shah rukh khan', 'shahrukh', 'srk'],
                    'shah rukh': ['shah rukh khan', 'shahrukh', 'srk'],
                    'salman': ['salman khan', 'salman'],
                    'salman khan': ['salman khan', 'salman'],
                    'ranveer': ['ranveer singh', 'ranveer'],
                    'ranveer singh': ['ranveer singh', 'ranveer'],
                    'varun': ['varun dhawan', 'varun'],
                    'varun dhawan': ['varun dhawan', 'varun'],
                    'madhavan': ['r. madhavan', 'madhavan', 'r madhavan'],
                    'r. madhavan': ['r. madhavan', 'madhavan', 'r madhavan'],
                    'alia': ['alia bhatt', 'alia'],
                    'alia bhatt': ['alia bhatt', 'alia'],
                    'deepika': ['deepika padukone', 'deepika'],
                    'deepika padukone': ['deepika padukone', 'deepika'],
                    'priyanka': ['priyanka chopra', 'priyanka'],
                    'priyanka chopra': ['priyanka chopra', 'priyanka']
                }
                
                detected_actor = None
                for actor_key, actor_variants in known_actors.items():
                    if actor_key in query_lower:
                        detected_actor = actor_variants
                        print(f"🎭 Detected actor search: '{actor_key}' - will filter to only this actor's videos!")
                        break
                
                if detected_actor:
                    # Check if this video's actors field contains ANY variant of the searched actor
                    actors_lower = actors.lower() if actors else ''
                    character_tags_lower = character_tags.lower() if character_tags else ''
                    combined_actor_text = f"{actors_lower} {character_tags_lower}"
                    
                    actor_found = any(variant in combined_actor_text for variant in detected_actor)
                    
                    if not actor_found:
                        print(f"   ⚠️ Skipping result - User searched for {detected_actor[0]} but video has actors: '{actors or 'Unknown'}'")
                        continue  # Skip this video - wrong actor!
                
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
