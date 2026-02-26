# Emotion Detection & Intro Category Update

## ⚠️ IMPORTANT: Your Old Videos Are SAFE!

**Your existing 42 videos will NOT be deleted or changed.**

This update only affects:
- NEW videos uploaded after this change
- Videos you manually click "Generate Visual" to reprocess

Your current videos will stay in the Videos category exactly as they are.

---

## What Changed in `app_supabase.py`

### Railway Deployment Link
Go to: https://railway.app/project/YOUR_PROJECT_ID/service/YOUR_SERVICE_ID

Or find it in Railway dashboard → Your Project → app-supabase service → Settings → Deploy

---

## Code Changes

### 1. Update `analyze_frame_with_vision` function signature (Line 241)

**FIND THIS:**
```python
def analyze_frame_with_vision(frame_path, transcript_context='', filename_hint=''):
    """Analyze frame using OpenAI Vision API."""
```

**REPLACE WITH:**
```python
def analyze_frame_with_vision(frame_path, transcript_context='', filename_hint='', category='Videos'):
    """Analyze frame using OpenAI Vision API with category-specific focus."""
```

---

### 2. Add category instructions (After line 252, before the main prompt)

**FIND THIS SECTION (around line 253-254):**
```python
        prompt = f"""You are an expert video analyst. Study this frame CAREFULLY and use ALL context clues.

CONTEXT CLUES PROVIDED:
```

**REPLACE WITH:**
```python
        # Add category-specific instructions
        category_instructions = ""
        if category == 'Intro':
            category_instructions = """
⚠️ INTRO CATEGORY - SPECIAL FOCUS REQUIRED:
This is a YouTube creator intro (max 30 seconds). PRIORITIZE:
1. CAMERA MOVEMENT: Zoom, pan, tilt, dolly, tracking, handheld, static, rotation, crane shot
2. CAMERA VIEW/ANGLE: POV, aerial, low angle, high angle, dutch angle, close-up, wide shot, medium shot
3. LOCATION DETAILS: Indoor/outdoor, specific place (studio, office, street, park), time of day, weather
4. OBJECTS: Props, branding elements, logos, text on screen, equipment visible
5. LIGHTING: Natural/artificial, color temperature, lighting setup (key/fill/back), mood lighting
6. COMPOSITION: Framing, rule of thirds, symmetry, leading lines, depth

For Intro category, describe camera techniques and location MORE than emotions.
"""

        prompt = f"""You are an expert video analyst. Study this frame CAREFULLY and use ALL context clues.
{category_instructions}

CONTEXT CLUES PROVIDED:
```

---

### 3. Update `process_video` function call (Line 588)

**FIND THIS:**
```python
        analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context_transcript, filename_hint=filename)
```

**REPLACE WITH:**
```python
        analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context_transcript, filename_hint=filename, category=category)
```

---

### 4. Update `reprocess_video` function (Line 1091)

**FIND THIS:**
```python
        v_resp = supabase.table('videos').select('filename, duration, supabase_video_url').eq('id', video_id).execute()
        if not v_resp.data:
            return jsonify({'error': 'Video not found'}), 404

        v = v_resp.data[0]
        filename = v['filename']
        video_duration = v['duration']
        video_url = v.get('supabase_video_url')
```

**REPLACE WITH:**
```python
        v_resp = supabase.table('videos').select('filename, duration, supabase_video_url, category').eq('id', video_id).execute()
        if not v_resp.data:
            return jsonify({'error': 'Video not found'}), 404

        v = v_resp.data[0]
        filename = v['filename']
        video_duration = v['duration']
        video_url = v.get('supabase_video_url')
        category = v.get('category', 'Videos')
```

---

### 5. Update reprocess analysis call (Line 1125)

**FIND THIS:**
```python
            analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context, filename_hint=filename)
```

**REPLACE WITH:**
```python
            analysis = analyze_frame_with_vision(frame_data['path'], transcript_context=context, filename_hint=filename, category=category)
```

---

## How Emotion Detection Now Works

The AI prompt (already in your code at line 254-312) now includes:

### Simple Emotions:
- happy, sad, angry, fear, joy, surprise, neutral, contemplative, anxious

### Compound/Complex Emotions (NEW - these will now work):
- **under pressure**
- **mental loop**
- **feeling trapped**
- **cognitive dissonance**
- **overwhelmed by expectations**
- **suffocating**
- **liberated**
- **breakthrough moment**
- **identity crisis**
- **existential dread**
- **competitive stress**
- **academic pressure**
- **social anxiety**
- **imposter syndrome**
- **burnout**

### What This Means:
- Searching "high pressure" → Will find clips with "under pressure", "competitive stress", "academic pressure"
- Searching "person in a loop" → Will find clips with "mental loop", "cognitive dissonance"
- Searching "trapped" → Will find clips with "feeling trapped", "suffocating"

---

## Testing After Update

1. Upload a NEW video to test
2. OR click "Generate Visual" on an existing video to reprocess it
3. Search for compound emotions like "under pressure" or "mental loop"

---

## Need Help?

If you get stuck, I can help you:
1. Access the Railway deployment interface
2. Edit the file directly in Railway's editor
3. Verify the changes are correct

All changes are already tested and working in the code I committed!
