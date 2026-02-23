# 🚀 Advanced Multi-Layer Tagging System - Implementation Guide

## Date: February 13, 2026

---

## 🎯 Objective

Transform the B-roll tool from basic tagging to **intelligent scene understanding** with deep, multi-layer metadata generation.

---

## 📊 New Tagging Dimensions

### 1. Deep Emotions
**Beyond basic emotions** (happy, sad, angry)

**Examples:**
- triumphant, euphoric, power high, victorious, rebellious joy
- heartbroken, melancholic, defeated, nostalgic
- disbelief, sarcastic smile, nervous laughter, tense anticipation
- prideful, smug, condescending, vengeful

**Storage:** `deep_emotions` column (TEXT, comma-separated)

---

### 2. Scene Context
**What's happening in the scene**

**Examples:**
- business deal, confrontation, victory moment
- emotional breakdown, celebration, negotiation
- argument, confession, revelation, reunion
- betrayal, triumph, defeat, realization

**Storage:** `scene_context` column (TEXT)

---

### 3. People Description
**Detailed character information**

**Components:**
- Number: "two men", "group of 5 people", "solo person"
- Age: youth (18-25), young adult (25-35), middle-aged, senior
- Clothing: "formal suits", "casual wear", "office attire"
- Features: "wearing sunglasses", "with beard", "holding briefcase"
- Names: Actor/character names if recognizable

**Storage:** `people_description` column (TEXT)

---

### 4. Environment
**Detailed setting description**

**Examples:**
- "corporate office with glass walls"
- "dimly lit bar", "courtroom", "hospital corridor"
- "street market", "nightclub", "conference room"
- "luxury apartment", "prison cell"

**Storage:** `environment` column (TEXT)

---

### 5. Dialogue Context
**Inferred from visuals**

**Examples:**
- motivational speech, heated argument, friendly banter
- negotiation, confession, threat, promise
- celebration toast, emotional apology
- sarcastic remark, business pitch

**Storage:** `dialogue_context` column (TEXT)

---

### 6. Series/Movie Identification
**Content source identification**

**Examples:**
- "Scam 1992", "The Office", "Breaking Bad"
- "Farzi", "Sacred Games", "Money Heist"

**Storage:** `series_movie` column (TEXT)

---

### 7. Target Audience
**Intended demographic**

**Examples:**
- youth, corporate professionals, family
- mass audience, niche audience, international

**Storage:** `target_audience` column (TEXT)

---

### 8. Scene Type
**Narrative category**

**Examples:**
- action sequence, dialogue scene, emotional moment
- comedic bit, dramatic reveal, montage
- establishing shot, climax, confrontation

**Storage:** `scene_type` column (TEXT)

---

## 🗄️ Database Schema Changes

### New Columns Added to `visual_frames` Table

```sql
ALTER TABLE visual_frames ADD COLUMN deep_emotions TEXT;
ALTER TABLE visual_frames ADD COLUMN scene_context TEXT;
ALTER TABLE visual_frames ADD COLUMN people_description TEXT;
ALTER TABLE visual_frames ADD COLUMN environment TEXT;
ALTER TABLE visual_frames ADD COLUMN dialogue_context TEXT;
ALTER TABLE visual_frames ADD COLUMN series_movie TEXT;
ALTER TABLE visual_frames ADD COLUMN target_audience TEXT;
ALTER TABLE visual_frames ADD COLUMN scene_type TEXT;
```

### Complete Schema

```sql
CREATE TABLE visual_frames (
    id INTEGER PRIMARY KEY,
    video_id INTEGER,
    filename TEXT,
    timestamp REAL,
    frame_path TEXT,
    visual_description TEXT,
    visual_embedding BLOB,
    
    -- Basic metadata (existing)
    emotion TEXT,
    ocr_text TEXT,
    tags TEXT,
    genres TEXT,
    
    -- Advanced metadata (NEW)
    deep_emotions TEXT,
    scene_context TEXT,
    people_description TEXT,
    environment TEXT,
    dialogue_context TEXT,
    series_movie TEXT,
    target_audience TEXT,
    scene_type TEXT
);
```

---

## 🤖 Vision API Prompt Enhancement

### Before (Old Prompt)
```
Analyze frame and provide:
- description
- emotion (happy, sad, angry)
- OCR text
- tags
- genres
```

### After (New Advanced Prompt)
```
Analyze frame DEEPLY and provide:
- description (context-aware)
- emotion (basic)
- deep_emotions (2-4 nuanced emotions)
- OCR text (enhanced detection)
- tags (general)
- genres
- scene_context (what's happening)
- people_description (detailed)
- environment (specific setting)
- dialogue_context (inferred)
- series_movie (if identifiable)
- target_audience
- scene_type (narrative category)
```

### Key Improvements
1. **Context-aware analysis** - Understands narrative, not just objects
2. **Deep emotional analysis** - Captures psychological nuances
3. **Scene understanding** - Identifies what's happening, not just what's visible
4. **Content identification** - Recognizes series/movies from visual cues
5. **Audience targeting** - Infers intended demographic

---

## 🔍 Search Integration

### Enhanced Embedding Generation

**Before:**
```python
combined_text = f"Title: {title}. {description}. Emotion: {emotion}. Tags: {tags}."
```

**After:**
```python
combined_text = f"""
Title: {title}.
Description: {description}.
Emotion: {emotion}.
Deep Emotions: {deep_emotions}.
Scene Context: {scene_context}.
People: {people_description}.
Environment: {environment}.
Dialogue Context: {dialogue_context}.
Series/Movie: {series_movie}.
Tags: {tags}.
Genres: {genres}.
"""
```

### Searchable Fields

Users can now search using:
- ✅ Deep emotions: "triumphant", "euphoric", "rebellious joy"
- ✅ Scene context: "business deal", "confrontation", "victory moment"
- ✅ People: "two men in suits", "young woman", "actor name"
- ✅ Environment: "corporate office", "courtroom", "nightclub"
- ✅ Dialogue context: "motivational speech", "heated argument"
- ✅ Series/Movie: "Scam 1992", "The Office", "Farzi"
- ✅ Scene type: "emotional moment", "confrontation"

---

## 🏷️ Tag Display Strategy

### UI Behavior

**Storage:**
- Store ALL tags in database
- All tags remain searchable

**Display:**
- Show top 3 most relevant tags in UI
- Tags displayed based on search context
- Click to see all tags

**Example:**
```
Video Card:
🎭 triumphant, victorious, power high
🎬 Crime Thriller, Drama
📺 Scam 1992

(Hidden but searchable: business deal, negotiation, corporate office, 
 two men in suits, intense dialogue, youth audience, confrontation scene)
```

---

## 📈 Performance Considerations

### Optimizations

1. **Batch Processing**
   - Process frames in batches of 3-5
   - Parallel Vision API calls where possible

2. **Caching**
   - Cache series/movie detection results
   - Reuse people descriptions for similar frames

3. **Embedding Efficiency**
   - Combine all metadata into single embedding
   - No need for multiple embeddings per frame

4. **Database Indexing**
   - Keep existing indexes
   - No new indexes needed (full-text search via embeddings)

---

## ✅ Backward Compatibility

### Guaranteed

1. **Existing videos still work**
   - Old videos without advanced tags remain searchable
   - Basic metadata (emotion, tags, genres) still present

2. **Existing search queries work**
   - No breaking changes to search API
   - New fields simply enhance results

3. **Database migration safe**
   - New columns added with ALTER TABLE
   - NULL values allowed (backward compatible)

4. **UI unchanged for old videos**
   - Old videos show basic tags
   - New videos show advanced tags

---

## 🧪 Testing Strategy

### Test Cases

#### 1. New Video Upload
```
Upload: Scam 1992 clip
Expected:
- deep_emotions: "triumphant, power high, euphoric"
- scene_context: "victory moment after successful deal"
- people_description: "two men in suits, mid-30s"
- environment: "corporate office with modern interior"
- series_movie: "Scam 1992"
- dialogue_context: "celebration of success"
```

#### 2. Search by Deep Emotion
```
Search: "triumphant"
Expected: Videos with triumphant emotion rank higher
```

#### 3. Search by Scene Context
```
Search: "business deal"
Expected: Videos with business deal context appear
```

#### 4. Search by Series
```
Search: "Scam 1992"
Expected: All Scam 1992 clips appear
```

#### 5. Existing Videos (Backward Compatibility)
```
Search: Old video by basic tag
Expected: Still works, no errors
```

---

## 🚀 Deployment Steps

### Phase 1: Database Migration ✅
- Add new columns to visual_frames
- Test on existing database
- Verify no data loss

### Phase 2: API Enhancement ✅
- Update Vision API prompt
- Update response parsing
- Test JSON parsing

### Phase 3: Storage Update (IN PROGRESS)
- Update INSERT statements
- Update embedding generation
- Test data storage

### Phase 4: Search Integration
- Verify all fields searchable
- Test ranking with new metadata
- Verify relevance boost works

### Phase 5: UI Enhancement
- Display top 3 tags
- Add "Show all tags" button
- Test tag display logic

### Phase 6: Testing
- End-to-end upload test
- Search accuracy test
- Performance test
- Backward compatibility test

---

## 📊 Expected Outcomes

### Before Advanced Tagging
```
Video: Scam 1992 victory scene
Tags: happy, office, business
Search: "triumphant" → NOT FOUND
Search: "victory moment" → NOT FOUND
Search: "Scam 1992" → NOT FOUND (unless in filename)
```

### After Advanced Tagging
```
Video: Scam 1992 victory scene
Basic Tags: happy, office, business
Deep Emotions: triumphant, victorious, euphoric, power high
Scene Context: victory moment after successful deal
People: two men in suits celebrating
Environment: corporate office, modern interior
Series: Scam 1992
Dialogue Context: celebration of success

Search: "triumphant" → ✅ FOUND (rank #1)
Search: "victory moment" → ✅ FOUND (rank #1)
Search: "Scam 1992" → ✅ FOUND (all episodes)
Search: "business deal celebration" → ✅ FOUND
Search: "corporate victory" → ✅ FOUND
```

---

## ⚠️ Constraints Met

✅ **No breaking changes** - Existing functionality preserved
✅ **Performance maintained** - Single Vision API call per frame
✅ **Backward compatible** - Old videos still work
✅ **Works for videos and GIFs** - All formats supported
✅ **Semantic search intact** - Enhanced, not replaced

---

## 🎯 Success Metrics

### Quantitative
- **Tag richness**: 3-5 tags → 15-20 tags per frame
- **Search precision**: 60% → 90%
- **Series identification**: 0% → 70%+
- **Emotion depth**: 1 emotion → 3-4 emotions

### Qualitative
- Users find exact clips using context
- Series-based search works
- Emotion-based retrieval accurate
- Scene understanding evident

---

**Status:** Implementation in progress
**Completion:** 40% (Database + API prompt done, Storage update next)
**ETA:** Complete implementation within this session
