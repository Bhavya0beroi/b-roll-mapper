# 🎬 Comprehensive Video Tool Upgrade - Implementation Plan

## Date: February 13, 2026

---

## 🎯 Objectives

1. **Accurate Visual Detection** - Correct scene descriptions
2. **Actor Recognition** - Detect actors from faces
3. **Series/Movie Identification** - Identify show names
4. **Better Tagging** - Relevant, comprehensive tags
5. **Batch Upload Support** - Handle 5+ videos simultaneously
6. **Per-Video Processing** - Individual "Generate Visuals" buttons

---

## 🚨 Current Problems (Diagnosed)

### Issue 1: Series Detection Inconsistent
```sql
Frame 1: Series = "Farzi" ✓
Frame 2: Series = "Scam 1992" ✗ (Should be Farzi)
```
**Problem:** Vision API making mistakes between similar Indian web series

### Issue 2: No Actor Names
```sql
People: "two men, mid-30s, wearing stylish attire"
```
**Expected:** "Shahid Kapoor, Bhuvan Arora"
**Problem:** Vision API not attempting face recognition

### Issue 3: Batch Upload Works but No Per-Video UI
**Current:** Upload processes all files sequentially ✓
**Problem:** No individual "Generate Visuals" button per video ✗

---

## ✅ Solutions

### Solution 1: Enhanced Vision Prompt for Actor Detection

**Add explicit actor recognition instructions:**
```
CRITICAL: ACTOR/CELEBRITY RECOGNITION
- If you recognize any actors/celebrities, NAME THEM SPECIFICALLY
- Examples: "Shahid Kapoor", "SRK", "Amitabh Bachchan", "Robert Downey Jr."
- Be confident: If face looks familiar, identify them
- If unsure: describe person instead ("young man in suit")
- Indian actors: Prioritize Bollywood/OTT actors
- International: Hollywood, Netflix stars
```

### Solution 2: Strengthen Series Detection

**Add confidence-based series identification:**
```
SERIES/MOVIE IDENTIFICATION
- Look for visual signatures: logos, watermarks, cinematography style
- Consider actors present (e.g., Shahid Kapoor often in Farzi)
- Check for consistent visual style across frames
- If 80%+ confident: Name the series
- If 50-80%: Add "possibly [name]"
- If <50%: Leave empty
```

### Solution 3: Add Per-Video "Generate Visuals" Button

**Frontend Changes:**
```javascript
// Each video card gets its own button
<button onclick="reprocessVideo(${video.id}, '${video.filename}')">
    Generate Visuals
</button>

// Button shows state:
- "Generate Visuals" (not processed)
- "Regenerate Visuals" (already has visuals)
- "Processing..." (in progress)
- "✓ Complete" (just finished)
```

### Solution 4: Batch Upload UI Improvements

**Add per-video progress tracking:**
```
Video 1: [✓ Uploaded] [⏳ Processing...] [Generate]
Video 2: [✓ Uploaded] [✓ Complete] [Regenerate]
Video 3: [⏳ Uploading...] [-] [-]
Video 4: [Pending] [-] [-]
Video 5: [Pending] [-] [-]
```

---

## 🔧 Implementation Steps

### Step 1: Enhance Vision Prompt ✅ (PRIORITY 1)
- Add actor recognition instructions
- Add series detection confidence levels
- Add visual signature recognition
- Emphasize Indian/Bollywood actors

### Step 2: Update Vision Response Parsing
- Handle actor names as array
- Store multiple actors separately
- Add confidence field for series

### Step 3: Frontend - Add Per-Video Buttons
- Modify video card template
- Add individual "Generate Visuals" button
- Add per-video processing state
- Show progress indicator per video

### Step 4: Backend - Individual Video Processing Endpoint
- Current `/reprocess/:id` works ✓
- Add loading state response
- Add WebSocket for real-time updates (optional)

### Step 5: Testing
- Test with Farzi video
- Verify actor detection
- Verify series identification
- Test batch upload (5 videos)
- Verify per-video buttons work

---

## 📊 Expected Results

### Before (Current Farzi Analysis)
```
Series: "Scam 1992" ✗
People: "two men, mid-30s, wearing stylish attire"
Tags: generic office, business tags
```

### After (Expected Farzi Analysis)
```
Series: "Farzi" ✓
Actors: ["Shahid Kapoor", "Bhuvan Arora"] ✓
People: "Shahid Kapoor and Bhuvan Arora standing confidently"
Tags: [
  "Farzi",
  "Shahid Kapoor",
  "Bhuvan Arora",
  "sunglasses",
  "stylish",
  "contemplation",
  "crime series",
  "indian web series",
  "two men looking upward"
]
```

---

## 🎯 Acceptance Criteria

✅ **Visual Accuracy**
- Scene descriptions match visuals
- No random/unreadable text
- Context-aware descriptions

✅ **Actor Detection**
- Recognizes Shahid Kapoor, other known actors
- Names them explicitly in people_description
- Falls back to description if unknown

✅ **Series Identification**
- Correctly identifies "Farzi"
- Consistent across all frames
- High confidence detection

✅ **Tagging Quality**
- Series name in tags
- Actor names in tags
- Mood/emotion tags
- Object/scene tags
- Genre tags

✅ **Batch Upload**
- Upload 5+ videos without UI break
- Each video independent
- Async processing works

✅ **Per-Video Processing**
- Each video has "Generate Visuals" button
- Button states: Generate/Processing/Complete
- Individual progress indication
- Can regenerate visuals per video

---

## 🚀 Implementation Priority

### High Priority (Immediate)
1. ✅ Enhanced Vision Prompt
2. ✅ Actor Recognition Logic
3. ⏳ Per-Video UI Buttons

### Medium Priority (Next)
4. ⏳ Frontend State Management
5. ⏳ Batch Upload UI Polish

### Low Priority (Future)
6. WebSocket real-time updates
7. Actor face database
8. Series logo detection

---

## 📝 Technical Details

### Actor Detection Approach

**Method 1: Vision API Recognition (Primary)**
- Rely on GPT-4o-mini's pre-trained knowledge
- Explicitly ask for celebrity/actor names
- Works for famous actors (Bollywood, Hollywood)

**Method 2: Face Recognition API (Future)**
- Use dedicated face recognition service
- Build actor face database
- Match faces to known actors

**Current Implementation:** Method 1 (Vision API)

### Series Detection Approach

**Visual Cues:**
1. Cinematography style (color grading, framing)
2. Actor presence (Shahid Kapoor → Farzi)
3. Production quality indicators
4. Watermarks/logos
5. Consistent visual signatures across frames

**Confidence Levels:**
- High (80%+): State confidently
- Medium (50-80%): "Possibly [name]"
- Low (<50%): Leave empty

---

## 🧪 Test Cases

### Test Case 1: Farzi Video
**Input:** Farzi video with Shahid Kapoor
**Expected:**
- Series: "Farzi"
- Actors: ["Shahid Kapoor", "Bhuvan Arora"]
- Tags include: farzi, shahid kapoor, crime series

### Test Case 2: Unknown Video
**Input:** Generic office video
**Expected:**
- Series: empty or "Unknown"
- Actors: descriptive ("man in suit")
- Tags: generic but accurate

### Test Case 3: Batch Upload
**Input:** 5 different videos
**Expected:**
- All upload successfully
- Each has independent state
- Each has "Generate Visuals" button
- UI doesn't break

### Test Case 4: Per-Video Processing
**Input:** Click "Generate Visuals" on one video
**Expected:**
- Only that video processes
- Button shows "Processing..."
- Completes with "✓ Complete"
- Can regenerate later

---

**Status:** Implementation in progress
**Next:** Enhance Vision Prompt → Test → Update Frontend
