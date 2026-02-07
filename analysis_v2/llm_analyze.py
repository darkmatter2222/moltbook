"""
MOLTBOOK LLM CATEGORICAL ANALYZER (Synchronous)
================================================
Runs LLM analysis on stratified sample using synchronous HTTP.
Fully resumable - saves progress every 50 comments.

Usage:
    python llm_analyze.py                    # Analyze 5000 comments
    python llm_analyze.py --sample 3000      # Custom sample size
"""

import pandas as pd
import numpy as np
import requests
import json
import os
import sys
import time
import re

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, 'features_traditional.csv')
LLM_PROGRESS_FILE = os.path.join(BASE_DIR, 'llm_progress.json')
ENRICHED_OUTPUT = os.path.join(BASE_DIR, 'analysis_enriched.csv')

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
LLM_SAMPLE_SIZE = 5000

LLM_DIMENSIONS = [
    "politeness", "humor", "sarcasm", "intelligence", "originality",
    "emotional_intensity", "sentiment", "helpfulness", "controversy",
    "confidence", "empathy", "assertiveness", "storytelling",
    "technical_depth", "persuasiveness", "authenticity", "engagement_bait",
    "warmth", "authority", "specificity", "provocativeness", "agreement",
    "call_to_action", "cultural_reference", "community_insider", "curiosity",
    "wit", "toxicity", "conciseness", "casual_tone",
]


def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Strip emoji for non-UTF8 terminals/file redirects
        clean = msg.encode('ascii', 'replace').decode('ascii')
        print(clean, flush=True)


# ============================================================
# STRATIFIED SAMPLING
# ============================================================

def stratified_sample(df, target_n):
    """Create stratified sample biased toward karma variance."""
    karma = df['karma']
    
    high = df[karma >= 10]
    medium = df[(karma >= 1) & (karma < 10)]
    zero = df[karma == 0]
    
    log(f"   Population: high(≥10)={len(high):,}, medium(1-9)={len(medium):,}, zero={len(zero):,}")
    
    samples = [high]  # Take ALL high karma
    remaining = target_n - len(high)
    
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
    log(f"   Selected: high={len(high):,}, medium={med_n:,}, zero={zero_n:,}")
    log(f"   Total sample: {len(result):,}")
    return result


# ============================================================
# LLM ANALYSIS (SYNCHRONOUS)
# ============================================================

def build_prompt(content):
    """Build efficient prompt for categorical rating."""
    truncated = content[:600] if len(content) > 600 else content
    dim_list = ", ".join(LLM_DIMENSIONS)
    
    return f"""Rate this social media comment on 30 dimensions. Use a 1-5 categorical scale:
1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High

Comment: "{truncated}"

Rate ALL of these dimensions: {dim_list}

Respond with ONLY valid JSON mapping each dimension name to an integer 1-5. Nothing else."""


def parse_llm_response(text):
    """Parse LLM response into dimension ratings."""
    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    
    text = text.strip()
    
    # Find JSON object
    if not text.startswith('{'):
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end+1]
    
    ratings = json.loads(text)
    
    # Validate: clamp all values to 1-5
    validated = {}
    for dim in LLM_DIMENSIONS:
        val = ratings.get(dim, 3)
        try:
            validated[dim] = max(1, min(5, int(float(val))))
        except (ValueError, TypeError):
            validated[dim] = 3
    
    return validated


def analyze_comment(session, content):
    """Analyze a single comment with the LLM (synchronous)."""
    if not content or len(str(content).strip()) < 3:
        return {dim: 3 for dim in LLM_DIMENSIONS}
    
    prompt = build_prompt(str(content))
    
    for attempt in range(3):
        try:
            response = session.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
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
                timeout=180
            )
            
            result = response.json()
            text = result.get("message", {}).get("content", "")
            return parse_llm_response(text)
            
        except Exception as e:
            if attempt < 2:
                log(f"      ⚠️ Retry {attempt+1}/3: {type(e).__name__}: {str(e)[:80]}")
                time.sleep(2 * (attempt + 1))
            else:
                return {dim: 3 for dim in LLM_DIMENSIONS}


def warmup_model(session):
    """Warm up model to load into VRAM."""
    log("   ⏳ Warming up model (loading into VRAM)...")
    try:
        response = session.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": "Say OK"}],
                "stream": False,
                "options": {"num_predict": 5}
            },
            timeout=300
        )
        msg = response.json().get('message', {}).get('content', '')[:50]
        log(f"   ✅ Model warmed up: {msg}")
        return True
    except Exception as e:
        log(f"   ❌ Cannot warm up model: {e}")
        return False


def run_llm_analysis(df_sample):
    """Run LLM analysis on sample with resume capability."""
    
    # Load existing progress
    existing_results = {}
    if os.path.exists(LLM_PROGRESS_FILE):
        try:
            with open(LLM_PROGRESS_FILE, 'r') as f:
                existing_results = json.load(f)
            log(f"   📂 Resuming: {len(existing_results)} comments already analyzed")
        except (json.JSONDecodeError, Exception):
            existing_results = {}
    
    # Filter to unanalyzed
    analyzed_ids = set(existing_results.keys())
    to_analyze = df_sample[~df_sample['comment_id'].astype(str).isin(analyzed_ids)]
    total_remaining = len(to_analyze)
    total_overall = len(df_sample)
    
    if total_remaining == 0:
        log("   ✅ All comments already analyzed!")
        return existing_results
    
    log(f"\n   🧠 LLM Analysis: {total_remaining} remaining of {total_overall} total")
    log(f"   Model: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    log(f"   Dimensions: {len(LLM_DIMENSIONS)}")
    log("")
    
    # Create session with connection pooling
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    
    # Check connectivity
    try:
        test = session.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        models = [m['name'] for m in test.json().get('models', [])]
        log(f"   ✅ Ollama connected. Available: {', '.join(models[:5])}")
    except Exception as e:
        log(f"   ❌ Cannot connect to Ollama at {OLLAMA_HOST}: {e}")
        return existing_results
    
    # Warm up
    if not warmup_model(session):
        return existing_results
    
    # Main analysis loop
    start_time = time.time()
    errors = 0
    
    for i, (idx, row) in enumerate(to_analyze.iterrows()):
        comment_id = str(row['comment_id'])
        content = row.get('content', '')
        
        try:
            ratings = analyze_comment(session, content)
        except KeyboardInterrupt:
            log(f"\n   ⚠️ Interrupted! Saving progress ({len(existing_results)} analyzed)...")
            with open(LLM_PROGRESS_FILE, 'w') as f:
                json.dump(existing_results, f)
            raise
        except Exception as e:
            errors += 1
            ratings = {dim: 3 for dim in LLM_DIMENSIONS}
        
        existing_results[comment_id] = ratings
        
        # Progress reporting every 25
        if (i + 1) % 25 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            eta = (total_remaining - i - 1) / rate if rate > 0 else 0
            eta_h = int(eta // 3600)
            eta_m = int((eta % 3600) // 60)
            pct = (len(existing_results) / total_overall) * 100
            log(f"   [{len(existing_results):,}/{total_overall:,}] "
                f"{pct:.1f}% | {rate:.2f}/s | "
                f"ETA: {eta_h}h{eta_m:02d}m | "
                f"Errors: {errors}")
        
        # Save progress every 50
        if (i + 1) % 50 == 0:
            with open(LLM_PROGRESS_FILE, 'w') as f:
                json.dump(existing_results, f)
    
    # Final save
    with open(LLM_PROGRESS_FILE, 'w') as f:
        json.dump(existing_results, f)
    
    elapsed = time.time() - start_time
    log(f"\n   ✅ LLM analysis complete!")
    log(f"   Analyzed: {i+1} comments in {elapsed:.0f}s ({(i+1)/max(elapsed,1):.2f}/s)")
    log(f"   Errors: {errors}")
    
    return existing_results


# ============================================================
# MERGE & SAVE
# ============================================================

def merge_and_save(df_all, llm_results):
    """Merge LLM results into the full enriched dataframe."""
    log(f"\n   Merging {len(llm_results):,} LLM results into {len(df_all):,} rows...")
    
    llm_rows = []
    for comment_id, ratings in llm_results.items():
        row = {'comment_id': comment_id}
        row.update(ratings)
        llm_rows.append(row)
    
    llm_df = pd.DataFrame(llm_rows)
    llm_df['comment_id'] = llm_df['comment_id'].astype(str)
    df_all['comment_id'] = df_all['comment_id'].astype(str)
    
    # Drop old LLM columns if they exist (from previous run)
    existing_llm_cols = [c for c in LLM_DIMENSIONS if c in df_all.columns]
    if existing_llm_cols:
        df_all = df_all.drop(columns=existing_llm_cols)
    
    final = df_all.merge(llm_df, on='comment_id', how='left')
    
    final.to_csv(ENRICHED_OUTPUT, index=False)
    
    llm_count = final[LLM_DIMENSIONS[0]].notna().sum()
    
    log(f"\n   💾 Saved: {ENRICHED_OUTPUT}")
    log(f"      Total rows: {len(final):,}")
    log(f"      Total columns: {len(final.columns)}")
    log(f"      LLM-analyzed: {llm_count:,}")
    
    return final


# ============================================================
# MAIN
# ============================================================

def main():
    # Parse args
    sample_size = LLM_SAMPLE_SIZE
    if '--sample' in sys.argv:
        idx = sys.argv.index('--sample')
        if idx + 1 < len(sys.argv):
            sample_size = int(sys.argv[idx + 1])
    
    log("=" * 70)
    log("🧠 MOLTBOOK LLM CATEGORICAL ANALYZER")
    log(f"   Model: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    log(f"   Dimensions: {len(LLM_DIMENSIONS)}")
    log(f"   Target sample: {sample_size:,}")
    log("=" * 70)
    
    # Load data (with traditional features)
    log(f"\n📥 Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    log(f"   Loaded {len(df):,} comments")
    
    # Stratified sample
    log(f"\n📊 Stratified Sampling...")
    sample = stratified_sample(df, sample_size)
    
    # Run LLM analysis
    log(f"\n" + "=" * 70)
    log("🔬 RUNNING LLM ANALYSIS")
    log("=" * 70)
    
    results = run_llm_analysis(sample)
    
    # Merge into full dataset
    log(f"\n" + "=" * 70)
    log("💾 MERGING RESULTS")
    log("=" * 70)
    
    merge_and_save(df, results)
    
    log(f"\n" + "=" * 70)
    log("✅ LLM ANALYSIS COMPLETE!")
    log("=" * 70)
    log(f"   Progress file: {LLM_PROGRESS_FILE}")
    log(f"   Enriched data: {ENRICHED_OUTPUT}")
    log(f"   Next step: python build_insights.py")
    log("")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("\n⚠️ Interrupted by user. Progress has been saved. Run again to resume.")
        sys.exit(0)
