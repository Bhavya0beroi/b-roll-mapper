"""
Script to replace analyze_frame_with_vision function with Gemini version
"""

# Read the file
with open('app_semantic.py', 'r') as f:
    lines = f.readlines()

# Find function start and end
func_start = None
func_end = None

for i, line in enumerate(lines):
    if 'def analyze_frame_with_vision(frame_path, transcript_context=\'\', filename_hint=\'\'):' in line:
        func_start = i
    if func_start is not None and i > func_start and line.startswith('def '):
        func_end = i
        break

print(f"Function found: lines {func_start + 1} to {func_end}")

# New function body
new_function = '''def analyze_frame_with_vision(frame_path, transcript_context='', filename_hint=''):
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
        
        # Call Gemini analyzer with user's Pro-Level B-Roll Asset Manager Prompt
        print(f"     🤖 Analyzing with Gemini Vision API...")
        result = analyze_frame_with_gemini(img, transcript_context, filename_hint)
        
        if result:
            print(f"     ✅ Gemini analysis complete")
            print(f"     📝 Description: {result.get('description', '')[:100]}...")
            print(f"     🎭 Series/Movie: {result.get('series_movie', 'Unknown')}")
            print(f"     👥 Characters: {result.get('people_description', '')[:60]}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Error analyzing frame with Gemini: {e}")
        import traceback
        traceback.print_exc()
        return None

'''

# Replace the function
new_lines = lines[:func_start] + [new_function + '\n'] + lines[func_end:]

# Write back
with open('app_semantic.py', 'w') as f:
    f.writelines(new_lines)

print(f"✅ Function replaced! Old: {func_end - func_start} lines, New: {len(new_function.split(chr(10)))} lines")
print(f"   Reduction: {func_end - func_start - len(new_function.split(chr(10)))} lines removed")
