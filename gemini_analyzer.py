"""
Gemini Vision API Analyzer for B-Roll
Uses Pro-Level B-Roll Asset Manager Prompt with NEW google-genai package
"""

from google import genai
from google.genai import types
from PIL import Image
import json
import os

def analyze_frame_with_gemini(img, transcript_context='', filename_hint=''):
    """
    Analyze frame using Gemini Vision with Pro-Level B-Roll Asset Manager Prompt.
    Returns structured JSON matching database schema.
    """
    
    # Build context
    context_info = ""
    if transcript_context:
        context_info += f"\n\n**Dialogue/Transcript:**\n{transcript_context}\n"
    if filename_hint:
        clean_hint = filename_hint.replace('_', ' ').replace('-', ' ').replace('.mp4', '').replace('.gif', '').replace('.mov', '')
        context_info += f"\n**Filename Hint:** {clean_hint}\n"
    
    # PRO-LEVEL B-ROLL ASSET MANAGER PROMPT (User's exact prompt - SIMPLIFIED for speed)
    prompt = f"""Act as a Senior Media Asset Manager and Film Curator.

Analyze this video frame to generate high-intent, "flavor-heavy" metadata for a professional B-roll library.

{context_info}

Return ONLY valid JSON with this exact structure:

{{
  "scene_summary": "2-3 sentence description of what's happening, including camera work and lighting",
  "series_movie": "Movie or Series Name (e.g., '3 Idiots', 'Farzi', 'The Office')",
  "characters": "Actor Name as Character Name (e.g., 'R. Madhavan as Farhan')",
  "emotion_tags": ["specific emotions - e.g., paternal-grief, euphoric, mad-joy, triumphant, NOT generic 'happy' or 'sad'"],
  "laugh_tags": ["laugh types if applicable - e.g., delirious-laugh, maniacal-laugh, nervous-chuckle, or empty array if no laughing"],
  "contextual_tags": ["scene vibe/genre - e.g., family-drama, crime-comedy, heist-moment, money-montage, home-setting"],
  "character_tags": ["character names, actor names, relationships - e.g., Farhan, R-Madhavan, father-son, duo"],
  "semantic_tags": ["visible objects/clothing - e.g., stack-of-cash, turban, sunglasses, police-uniform, saree"]
}}

CRITICAL RULES:
1. Generate 8-15 tags per category (be hyper-specific, not generic)
2. If it's an EMOTIONAL scene (grief, tears, sadness) → DO NOT add comedy/playful tags
3. If it's a COMEDY scene → DO NOT add grief/sorrow tags
4. Identify RELATIONSHIPS correctly:
   - Age difference + home setting = FAMILY (father-son, mother-daughter, NOT "male-friendship")
   - Same age + casual = FRIENDS (male-friendship, bromance)
5. Mention CLOTHING in semantic_tags (turban, suit, saree, uniform, sunglasses, helmet, etc.)
6. Return ONLY the JSON, no markdown, no extra text
"""

    try:
        # Initialize Gemini client
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Convert PIL Image to bytes for Gemini
        import io
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        # Generate response using gemini-1.5-flash (fast and reliable)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=img_bytes,
                    mime_type='image/jpeg'
                ),
                prompt
            ]
        )
        
        result_text = response.text.strip()
        
        # Clean up response (remove markdown code blocks if present)
        if result_text.startswith('```'):
            lines = result_text.split('\n')
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's just ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            result_text = '\n'.join(lines).strip()
        
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        result = json.loads(result_text)
        
        # Map Gemini response to database schema
        emotion_tags_list = result.get('emotion_tags', [])
        laugh_tags_list = result.get('laugh_tags', [])
        contextual_tags_list = result.get('contextual_tags', [])
        character_tags_list = result.get('character_tags', [])
        semantic_tags_list = result.get('semantic_tags', [])
        
        # Combine all tags for the legacy 'tags' field
        all_tags = character_tags_list + semantic_tags_list
        
        # Extract actor name from "Actor as Character" format
        characters_str = result.get('characters', '')
        actor_name = ''
        if ' as ' in characters_str:
            actor_name = characters_str.split(' as ')[0].strip()
        elif characters_str and characters_str != 'Unknown':
            actor_name = characters_str
        
        return {
            'description': result.get('scene_summary', 'Video frame'),
            'emotion': emotion_tags_list[0] if emotion_tags_list else 'neutral',
            'deep_emotions': ', '.join(emotion_tags_list),
            'ocr_text': '',
            'tags': ', '.join(all_tags),
            'genres': 'Drama',
            'scene_context': result.get('scene_summary', ''),
            'people_description': result.get('characters', ''),
            'actors': actor_name,
            'environment': result.get('scene_summary', ''),
            'dialogue_context': transcript_context if transcript_context else '',
            'series_movie': result.get('series_movie', 'Unknown'),
            'media_type': 'Movie',
            'target_audience': 'General',
            'scene_type': 'dramatic',
            # Categorized tags (return as strings, not lists)
            'emotion_tags': ', '.join(emotion_tags_list),
            'laugh_tags': ', '.join(laugh_tags_list),
            'contextual_tags': ', '.join(contextual_tags_list),
            'character_tags': ', '.join(character_tags_list),
            'semantic_tags': ', '.join(semantic_tags_list)
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Gemini JSON response: {e}")
        print(f"   Raw response: {result_text[:500] if 'result_text' in locals() else 'No response'}")
        return None
    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        import traceback
        traceback.print_exc()
        return None
