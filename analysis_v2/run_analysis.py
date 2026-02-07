"""
MOLTBOOK KARMA ANALYSIS ENGINE v2
==================================
World-class NLP + LLM analysis of 100k+ comments.
Extracts 49 dimensions to find the karma recipe.

Phase 1: Traditional NLP Feature Extraction (all 100k comments, instant)
Phase 2: LLM Categorical Analysis (stratified sample, GPU-powered, resumable)

Usage:
    python run_analysis.py              # Run all phases
    python run_analysis.py --phase 1    # Traditional NLP only (fast)
    python run_analysis.py --phase 2    # LLM analysis only (slow, resumable)
"""

import pandas as pd
import numpy as np
import httpx
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime


def log(msg):
    """Print with immediate flush for background process visibility."""
    print(msg, flush=True)

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, 'comments_raw_v2.csv')
TRADITIONAL_OUTPUT = os.path.join(BASE_DIR, 'features_traditional.csv')
LLM_PROGRESS_FILE = os.path.join(BASE_DIR, 'llm_progress.json')
ENRICHED_OUTPUT = os.path.join(BASE_DIR, 'analysis_enriched.csv')

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')

LLM_SAMPLE_SIZE = 5000  # Stratified sample for LLM analysis

# ============================================================
# 30 LLM-ASSESSED CATEGORICAL DIMENSIONS (1-5 scale)
# ============================================================

LLM_DIMENSIONS = [
    "politeness",           # 1: Respectfulness and courtesy
    "humor",                # 2: Funniness and entertainment value
    "sarcasm",              # 3: Ironic or mocking undertone
    "intelligence",         # 4: Intellectual sophistication
    "originality",          # 5: Uniqueness and creative thinking
    "emotional_intensity",  # 6: How emotionally charged
    "sentiment",            # 7: Overall positivity (1=very negative, 5=very positive)
    "helpfulness",          # 8: Usefulness to readers
    "controversy",          # 9: Likely to spark debate
    "confidence",           # 10: Self-assuredness of the author
    "empathy",              # 11: Understanding of others' feelings
    "assertiveness",        # 12: Boldness and directness
    "storytelling",         # 13: Narrative quality
    "technical_depth",      # 14: Domain expertise shown
    "persuasiveness",       # 15: How convincing the argument is
    "authenticity",         # 16: How genuine it feels
    "engagement_bait",      # 17: Designed to provoke reactions
    "warmth",               # 18: Friendliness and approachability
    "authority",            # 19: Expert or authoritative signaling
    "specificity",          # 20: How detailed and concrete
    "provocativeness",      # 21: How attention-grabbing or edgy
    "agreement",            # 22: Alignment with mainstream/common views
    "call_to_action",       # 23: Encourages response or action
    "cultural_reference",   # 24: Uses memes, pop culture, community lingo
    "community_insider",    # 25: Shows in-group/community knowledge
    "curiosity",            # 26: Shows interest, asks questions
    "wit",                  # 27: Clever wordplay and smart humor
    "toxicity",             # 28: Hostile, harmful, or mean-spirited
    "conciseness",          # 29: Says a lot with few words
    "casual_tone",          # 30: Informal, relaxed communication style
]

# Traditional NLP feature names (computed, no LLM needed)
TRADITIONAL_FEATURES = [
    'word_count', 'char_count', 'sentence_count', 'avg_word_length',
    'unique_word_ratio', 'emoji_count', 'has_emoji',
    'lobster_emoji_count', 'has_lobster',
    'question_count', 'has_question',
    'exclamation_count', 'has_exclamation',
    'caps_ratio', 'all_caps_words',
    'punctuation_density', 'has_url',
    'first_person_count', 'second_person_count',
    'newline_count',
]


# ============================================================
# PHASE 1: TRADITIONAL NLP FEATURE EXTRACTION
# ============================================================

def compute_traditional_features(df):
    """Compute traditional NLP features for ALL comments - instant, no GPU needed."""
    log("\n" + "=" * 70)
    log("📊 PHASE 1: Traditional NLP Feature Extraction")
    log("=" * 70)
    
    content = df['content'].fillna('').astype(str)
    features = pd.DataFrame(index=df.index)
    
    # --- Lexical features ---
    log("   Computing lexical features...")
    features['word_count'] = content.str.split().str.len().fillna(0).astype(int)
    features['char_count'] = content.str.len()
    features['sentence_count'] = content.str.count(r'[.!?]+').clip(lower=1)
    features['avg_word_length'] = content.apply(
        lambda x: np.mean([len(w) for w in x.split()]) if x.strip() else 0
    )
    
    # Vocabulary richness
    def unique_ratio(text):
        words = text.lower().split()
        return len(set(words)) / len(words) if words else 0
    features['unique_word_ratio'] = content.apply(unique_ratio)
    
    # --- Emoji features ---
    log("   Computing emoji features...")
    emoji_pattern = re.compile(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U00002702-\U000027B0'
        r'\U0001F1E0-\U0001F1FF]'
    )
    features['emoji_count'] = content.apply(lambda x: len(emoji_pattern.findall(x)))
    features['has_emoji'] = (features['emoji_count'] > 0).astype(int)
    
    # Lobster emoji - known karma driver on this platform
    features['lobster_emoji_count'] = content.str.count('🦞')
    features['has_lobster'] = (features['lobster_emoji_count'] > 0).astype(int)
    
    # --- Punctuation features ---
    log("   Computing punctuation features...")
    features['question_count'] = content.str.count(r'\?')
    features['has_question'] = (features['question_count'] > 0).astype(int)
    features['exclamation_count'] = content.str.count(r'!')
    features['has_exclamation'] = (features['exclamation_count'] > 0).astype(int)
    
    # --- Capitalization features ---
    log("   Computing capitalization features...")
    features['caps_ratio'] = content.apply(
        lambda x: sum(1 for c in x if c.isupper()) / max(len(x), 1)
    )
    features['all_caps_words'] = content.apply(
        lambda x: sum(1 for w in x.split() if w.isupper() and len(w) > 1)
    )
    
    # --- Structural features ---
    log("   Computing structural features...")
    features['punctuation_density'] = content.apply(
        lambda x: sum(1 for c in x if c in '.,;:!?-()[]{}') / max(len(x), 1)
    )
    features['has_url'] = content.str.contains(r'https?://', regex=True).astype(int)
    features['first_person_count'] = content.str.lower().str.count(r'\b(i|me|my|mine|myself)\b')
    features['second_person_count'] = content.str.lower().str.count(r'\b(you|your|yours|yourself)\b')
    features['newline_count'] = content.str.count(r'\n')
    
    log(f"\n   ✅ Computed {len(features.columns)} traditional features for {len(features):,} comments")
    return features


# ============================================================
# PHASE 2: LLM CATEGORICAL ANALYSIS
# ============================================================

def stratified_sample(df, target_n=5000):
    """Create stratified sample biased toward karma variance for meaningful correlation."""
    log(f"\n   📊 Stratified Sampling (target: {target_n:,})...")
    
    karma = df['karma']
    
    # Define strata
    high = df[karma >= 10]
    medium = df[(karma >= 1) & (karma < 10)]
    zero = df[karma == 0]
    
    log(f"      Population: high(≥10)={len(high):,}, medium(1-9)={len(medium):,}, zero={len(zero):,}")
    
    samples = []
    
    # Take ALL high karma comments (rare and valuable for analysis)
    samples.append(high)
    remaining = target_n - len(high)
    
    # Split remaining between medium and zero
    med_n = min(len(medium), max(remaining * 2 // 3, 500))
    zero_n = min(len(zero), remaining - med_n)
    
    if med_n < len(medium):
        samples.append(medium.sample(med_n, random_state=42))
    else:
        samples.append(medium)
        med_n = len(medium)
    
    if zero_n > 0:
        if zero_n < len(zero):
            samples.append(zero.sample(zero_n, random_state=42))
        else:
            samples.append(zero)
            zero_n = len(zero)
    
    result = pd.concat(samples).drop_duplicates(subset='comment_id')
    log(f"      Selected: high={len(high):,}, medium={med_n:,}, zero={zero_n:,}")
    log(f"      Total sample: {len(result):,}")
    return result


class LLMAnalyzer:
    """Async LLM-based comment analyzer with resume capability."""
    
    def __init__(self):
        self.host = OLLAMA_HOST
        self.model = OLLAMA_MODEL
        self.dimensions = LLM_DIMENSIONS
        self.errors = 0
        self.processed = 0
    
    def build_prompt(self, content):
        """Build an efficient prompt for categorical rating."""
        truncated = content[:600] if len(content) > 600 else content
        
        dim_list = ", ".join(self.dimensions)
        
        return f"""Rate this social media comment on 30 dimensions. Use a 1-5 categorical scale:
1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High

Comment: "{truncated}"

Rate ALL of these dimensions: {dim_list}

Respond with ONLY valid JSON mapping each dimension name to an integer 1-5. Nothing else."""

    async def warmup(self, client):
        """Warm up the model (triggers VRAM loading) with a tiny request."""
        log("   ⏳ Warming up model (loading into VRAM)...")
        try:
            response = await client.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "stream": False,
                    "options": {"num_predict": 5}
                },
                timeout=300.0
            )
            log(f"   ✅ Model warmed up: {response.json().get('message', {}).get('content', '')[:50]}")
        except Exception as e:
            log(f"   ⚠️ Warmup issue (will retry on first comment): {e}")

    async def analyze_one(self, client, content):
        """Analyze a single comment with the LLM."""
        if not content or len(str(content).strip()) < 3:
            return {dim: 3 for dim in self.dimensions}
        
        prompt = self.build_prompt(str(content))
        
        for attempt in range(3):
            try:
                response = await client.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert comment quality analyzer. Rate comments on categorical scales. Respond with ONLY a valid JSON object mapping 30 dimension names to integers 1-5. No explanations, no markdown code blocks, no other text."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.15,
                            "num_predict": 400,
                        }
                    },
                    timeout=180.0
                )
                
                result = response.json()
                text = result.get("message", {}).get("content", "")
                
                # Parse JSON - handle markdown code blocks
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                # Try to find JSON object in text
                text = text.strip()
                if not text.startswith('{'):
                    # Find first { and last }
                    start = text.find('{')
                    end = text.rfind('}')
                    if start >= 0 and end > start:
                        text = text[start:end+1]
                
                ratings = json.loads(text)
                
                # Validate: clamp all values to 1-5
                validated = {}
                for dim in self.dimensions:
                    val = ratings.get(dim, 3)
                    try:
                        validated[dim] = max(1, min(5, int(float(val))))
                    except (ValueError, TypeError):
                        validated[dim] = 3
                
                return validated
                
            except asyncio.CancelledError:
                raise  # Don't swallow cancellation
            except Exception as e:
                if attempt < 2:
                    log(f"   ⚠️ Retry {attempt+1}/3: {type(e).__name__}: {str(e)[:80]}")
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    self.errors += 1
                    return {dim: 3 for dim in self.dimensions}
    
    async def analyze_sample(self, df):
        """Analyze all comments in the sample with resume capability."""
        
        # Load existing progress
        existing_results = {}
        if os.path.exists(LLM_PROGRESS_FILE):
            try:
                with open(LLM_PROGRESS_FILE, 'r') as f:
                    existing_results = json.load(f)
                log(f"   📂 Resuming: {len(existing_results)} comments already analyzed")
            except json.JSONDecodeError:
                existing_results = {}
        
        # Filter to unanalyzed comments
        analyzed_ids = set(existing_results.keys())
        to_analyze = df[~df['comment_id'].astype(str).isin(analyzed_ids)]
        total_remaining = len(to_analyze)
        total_overall = len(df)
        
        if total_remaining == 0:
            log("   ✅ All comments in sample already analyzed!")
            return existing_results
        
        log(f"\n   🧠 LLM Analysis: {total_remaining} remaining of {total_overall} total")
        log(f"   Model: {self.model} @ {self.host}")
        log(f"   Dimensions: {len(self.dimensions)}")
        log("")
        
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Quick connectivity check
            try:
                test = await client.get(f"{self.host}/api/tags", timeout=10.0)
                models = [m['name'] for m in test.json().get('models', [])]
                log(f"   ✅ Ollama connected. Available models: {', '.join(models[:5])}")
            except Exception as e:
                log(f"   ❌ Cannot connect to Ollama at {self.host}: {e}")
                log(f"   Make sure Ollama is running at {self.host}")
                return existing_results
            
            # Warm up model (loads into VRAM)
            await self.warmup(client)
            
            for i, (idx, row) in enumerate(to_analyze.iterrows()):
                comment_id = str(row['comment_id'])
                content = row.get('content', '')
                
                ratings = await self.analyze_one(client, content)
                existing_results[comment_id] = ratings
                self.processed += 1
                
                # Progress reporting
                if (i + 1) % 25 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    eta = (total_remaining - i - 1) / rate if rate > 0 else 0
                    eta_h = int(eta // 3600)
                    eta_m = int((eta % 3600) // 60)
                    pct = (len(existing_results) / total_overall) * 100
                    log(f"   [{len(existing_results):,}/{total_overall:,}] "
                        f"{pct:.1f}% | {rate:.1f} comments/s | "
                        f"ETA: {eta_h}h{eta_m:02d}m | "
                        f"Errors: {self.errors}")
                
                # Save progress every 50 comments
                if (i + 1) % 50 == 0:
                    with open(LLM_PROGRESS_FILE, 'w') as f:
                        json.dump(existing_results, f)
        
        # Final save
        with open(LLM_PROGRESS_FILE, 'w') as f:
            json.dump(existing_results, f)
        
        elapsed = time.time() - start_time
        log(f"\n   ✅ LLM analysis complete!")
        log(f"   Analyzed: {self.processed} comments in {elapsed:.0f}s ({self.processed/max(elapsed,1):.1f}/s)")
        log(f"   Errors: {self.errors}")
        
        return existing_results


# ============================================================
# MERGE & SAVE
# ============================================================

def merge_and_save(df_with_traditional, llm_results=None):
    """Merge traditional features with LLM results and save enriched CSV."""
    
    df = df_with_traditional.copy()
    
    if llm_results:
        log(f"\n   Merging {len(llm_results):,} LLM results...")
        
        llm_rows = []
        for comment_id, ratings in llm_results.items():
            row = {'comment_id': comment_id}
            row.update(ratings)
            llm_rows.append(row)
        
        llm_df = pd.DataFrame(llm_rows)
        llm_df['comment_id'] = llm_df['comment_id'].astype(str)
        df['comment_id'] = df['comment_id'].astype(str)
        
        df = df.merge(llm_df, on='comment_id', how='left', suffixes=('', '_llm'))
    
    df.to_csv(ENRICHED_OUTPUT, index=False)
    
    # Count how many have LLM features
    llm_count = 0
    if LLM_DIMENSIONS[0] in df.columns:
        llm_count = df[LLM_DIMENSIONS[0]].notna().sum()
    
    log(f"\n   💾 Saved enriched data: {ENRICHED_OUTPUT}")
    log(f"      Total rows: {len(df):,}")
    log(f"      Total columns: {len(df.columns)}")
    log(f"      LLM-analyzed rows: {llm_count:,}")
    
    return df


# ============================================================
# MAIN
# ============================================================

async def run_phase1(df):
    """Phase 1: Traditional NLP features for all comments."""
    features = compute_traditional_features(df)
    df_enriched = pd.concat([df, features], axis=1)
    
    # Save intermediate
    df_enriched.to_csv(TRADITIONAL_OUTPUT, index=False)
    log(f"   💾 Saved: {TRADITIONAL_OUTPUT}")
    
    # Quick stats
    log(f"\n   📈 Quick Traditional Feature Correlations with Karma:")
    numeric_cols = features.columns.tolist()
    karma = df['karma']
    
    correlations = []
    for col in numeric_cols:
        try:
            corr = features[col].corr(karma, method='spearman')
            if not np.isnan(corr):
                correlations.append((col, corr))
        except Exception:
            pass
    
    correlations.sort(key=lambda x: abs(x[1]), reverse=True)
    log(f"   {'Feature':<25} {'Spearman r':>12}")
    log(f"   {'-'*25} {'-'*12}")
    for col, corr in correlations[:15]:
        indicator = "🔥" if abs(corr) > 0.1 else "  "
        log(f"   {indicator} {col:<23} {corr:>+.4f}")
    
    return df_enriched


async def run_phase2(df):
    """Phase 2: LLM categorical analysis on stratified sample."""
    log("\n" + "=" * 70)
    log("🧠 PHASE 2: LLM Categorical Analysis (30 Dimensions)")
    log("=" * 70)
    
    # Stratified sample
    sample = stratified_sample(df, LLM_SAMPLE_SIZE)
    
    # Run LLM analysis
    analyzer = LLMAnalyzer()
    results = await analyzer.analyze_sample(sample)
    
    return results


async def main():
    # Parse args
    phase = 'all'
    if '--phase' in sys.argv:
        idx = sys.argv.index('--phase')
        if idx + 1 < len(sys.argv):
            phase = sys.argv[idx + 1]
    
    log("=" * 70)
    log("🚀 MOLTBOOK KARMA ANALYSIS ENGINE v2")
    log(f"   Phase: {phase}")
    log(f"   LLM: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    log(f"   Target sample: {LLM_SAMPLE_SIZE:,} comments")
    log(f"   LLM Dimensions: {len(LLM_DIMENSIONS)}")
    log(f"   Traditional Features: {len(TRADITIONAL_FEATURES)}")
    log("=" * 70)
    
    # Load data
    log(f"\n📥 Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    log(f"   Loaded {len(df):,} comments")
    
    # Karma distribution overview
    log(f"\n   Karma Distribution:")
    log(f"      karma=0: {len(df[df['karma']==0]):,}")
    log(f"      karma 1-9: {len(df[(df['karma']>=1) & (df['karma']<10)]):,}")
    log(f"      karma 10-49: {len(df[(df['karma']>=10) & (df['karma']<50)]):,}")
    log(f"      karma 50+: {len(df[df['karma']>=50]):,}")
    
    llm_results = None
    
    if phase in ('1', 'all'):
        df_enriched = await run_phase1(df)
    else:
        # Load traditional features if already computed
        if os.path.exists(TRADITIONAL_OUTPUT):
            df_enriched = pd.read_csv(TRADITIONAL_OUTPUT)
            log(f"   📂 Loaded pre-computed traditional features from {TRADITIONAL_OUTPUT}")
        else:
            df_enriched = await run_phase1(df)
    
    if phase in ('2', 'all'):
        llm_results = await run_phase2(df_enriched)
    elif os.path.exists(LLM_PROGRESS_FILE):
        # Load existing LLM results
        with open(LLM_PROGRESS_FILE, 'r') as f:
            llm_results = json.load(f)
        log(f"   📂 Loaded {len(llm_results):,} LLM results from {LLM_PROGRESS_FILE}")
    
    # Merge and save
    final_df = merge_and_save(df_enriched, llm_results)
    
    log("\n" + "=" * 70)
    log("✅ ANALYSIS ENGINE COMPLETE")
    log("=" * 70)
    log(f"   Output: {ENRICHED_OUTPUT}")
    log(f"   Next: python build_insights.py")
    log("")


if __name__ == '__main__':
    asyncio.run(main())
