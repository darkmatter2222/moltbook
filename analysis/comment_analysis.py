"""
Moltbook Comment Analysis Script
Fetches comments, extracts attributes using LLM, and builds correlation matrix with karma
"""

import httpx
import json
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import os

# API Configuration (loaded from environment or .env)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

MOLTBOOK_API = "https://www.moltbook.com/api/v1"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OUR_AGENT = os.getenv("MOLTBOOK_AGENT_NAME", "Darkmatter2222")
API_KEY = os.getenv("MOLTBOOK_API_KEY", "")

# Attributes to extract (categorical 1-10 scale)
ATTRIBUTES = [
    "politeness",
    "intelligence", 
    "thoughtfulness",
    "humor",
    "relevance",
    "originality",
    "engagement_potential",
    "emotional_depth",
    "clarity",
    "helpfulness"
]

async def fetch_posts(limit: int = 30) -> list:
    """Fetch posts from Moltbook"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{MOLTBOOK_API}/posts?sort=hot&limit={limit}")
        data = response.json()
        return data.get("posts", [])

async def fetch_comments_for_post(post_id: str) -> list:
    """Fetch comments for a specific post"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{MOLTBOOK_API}/posts/{post_id}/comments")
        data = response.json()
        return data.get("comments", [])

async def fetch_our_agent_activity() -> dict:
    """Fetch our agent's activity"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{MOLTBOOK_API}/agents/status", headers=headers)
        return response.json()

def flatten_comments(comments: list, post_id: str, post_title: str, depth: int = 0) -> list:
    """Flatten nested comment structure"""
    flat = []
    for c in comments:
        flat.append({
            "comment_id": c.get("id"),
            "post_id": post_id,
            "post_title": post_title[:50],
            "author": c.get("author", {}).get("name", "Unknown"),
            "content": c.get("content", ""),
            "upvotes": c.get("upvotes", 0),
            "downvotes": c.get("downvotes", 0),
            "karma": c.get("upvotes", 0) - c.get("downvotes", 0),
            "depth": depth,
            "created_at": c.get("created_at", "")
        })
        # Recursively get replies
        if c.get("replies"):
            flat.extend(flatten_comments(c["replies"], post_id, post_title, depth + 1))
    return flat

async def analyze_comment_with_llm(comment: str) -> dict:
    """Use LLM to extract categorical attributes from a comment"""
    prompt = f"""Analyze this comment and rate each attribute on a scale of 1-10 (1=poor, 10=excellent).
This is a CATEGORICAL scale where each number represents a distinct category of quality.

Comment: "{comment[:500]}"

Rate these attributes (respond with ONLY the JSON, no explanation):
- politeness: How polite and respectful is the comment?
- intelligence: How intellectually sophisticated is the comment?
- thoughtfulness: How much thought/consideration went into it?
- humor: How funny or witty is it? (1=not at all, 10=hilarious)
- relevance: How relevant is it to the discussion?
- originality: How unique/creative is the perspective?
- engagement_potential: How likely is it to spark further discussion?
- emotional_depth: How emotionally resonant or authentic?
- clarity: How clear and well-expressed?
- helpfulness: How useful or valuable to readers?

Respond with ONLY valid JSON like: {{"politeness": 7, "intelligence": 8, ...}}"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a comment quality analyzer. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
            )
            result = response.json()
            content = result.get("message", {}).get("content", "{}")
            
            # Try to parse JSON from response
            # Sometimes the model wraps it in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return {attr: 5 for attr in ATTRIBUTES}  # Default to middle value

async def collect_comments(num_posts: int = 15, max_comments_per_post: int = 20) -> pd.DataFrame:
    """Collect comments from multiple posts"""
    print(f"Fetching {num_posts} posts...")
    posts = await fetch_posts(num_posts)
    
    all_comments = []
    
    for i, post in enumerate(posts):
        post_id = post.get("id")
        post_title = post.get("title", "")
        print(f"[{i+1}/{len(posts)}] Fetching comments for: {post_title[:40]}...")
        
        try:
            comments = await fetch_comments_for_post(post_id)
            flat = flatten_comments(comments, post_id, post_title)
            
            # Take a sample if too many
            if len(flat) > max_comments_per_post:
                # Mix of high karma and random
                flat.sort(key=lambda x: x["karma"], reverse=True)
                top_karma = flat[:max_comments_per_post // 2]
                rest = flat[max_comments_per_post // 2:]
                import random
                random_sample = random.sample(rest, min(len(rest), max_comments_per_post // 2))
                flat = top_karma + random_sample
            
            all_comments.extend(flat)
            print(f"   Got {len(flat)} comments")
        except Exception as e:
            print(f"   Error: {e}")
        
        await asyncio.sleep(0.5)  # Rate limiting
    
    return pd.DataFrame(all_comments)

async def analyze_comments(df: pd.DataFrame, sample_size: int = 100) -> pd.DataFrame:
    """Analyze comments with LLM to extract attributes"""
    
    # Sample if too many
    if len(df) > sample_size:
        # Stratified sample: mix of karma levels
        df_sorted = df.sort_values("karma")
        indices = np.linspace(0, len(df)-1, sample_size, dtype=int)
        df = df.iloc[indices].copy()
    
    print(f"\nAnalyzing {len(df)} comments with LLM...")
    
    results = []
    for i, row in df.iterrows():
        print(f"[{len(results)+1}/{len(df)}] Analyzing comment by {row['author']}...", end=" ")
        
        attrs = await analyze_comment_with_llm(row["content"])
        
        result = row.to_dict()
        result.update(attrs)
        results.append(result)
        
        print(f"karma={row['karma']}")
        
        await asyncio.sleep(0.3)  # Don't overwhelm Ollama
    
    return pd.DataFrame(results)

def build_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Build correlation matrix between attributes and karma"""
    numeric_cols = ATTRIBUTES + ["karma", "upvotes", "downvotes"]
    available_cols = [c for c in numeric_cols if c in df.columns]
    
    corr_matrix = df[available_cols].corr()
    return corr_matrix

def display_results(df: pd.DataFrame, corr: pd.DataFrame):
    """Display analysis results"""
    print("\n" + "="*80)
    print("COMMENT ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\nTotal comments analyzed: {len(df)}")
    print(f"Our agent (Darkmatter2222) comments: {len(df[df['author'] == OUR_AGENT])}")
    
    print("\n--- Attribute Statistics ---")
    for attr in ATTRIBUTES:
        if attr in df.columns:
            print(f"{attr:25} mean={df[attr].mean():.2f}  std={df[attr].std():.2f}")
    
    print("\n--- Karma Statistics ---")
    print(f"Mean karma: {df['karma'].mean():.2f}")
    print(f"Median karma: {df['karma'].median():.2f}")
    print(f"Max karma: {df['karma'].max()}")
    
    print("\n" + "="*80)
    print("CORRELATION MATRIX: Attributes vs Karma")
    print("="*80)
    
    # Sort by correlation with karma
    if "karma" in corr.columns:
        karma_corr = corr["karma"].drop(["karma", "upvotes", "downvotes"], errors="ignore")
        karma_corr = karma_corr.sort_values(ascending=False)
        
        print("\nCorrelation with Karma (sorted):")
        print("-" * 40)
        for attr, value in karma_corr.items():
            bar = "█" * int(abs(value) * 20)
            sign = "+" if value > 0 else "-"
            print(f"{attr:25} {sign}{abs(value):.3f}  {bar}")
    
    print("\n--- Full Correlation Matrix ---")
    print(corr.round(3).to_string())
    
    return karma_corr

async def main():
    """Main analysis pipeline"""
    print("🦞 Moltbook Comment Analysis")
    print("="*50)
    
    # Step 1: Collect comments
    df_raw = await collect_comments(num_posts=15, max_comments_per_post=30)
    print(f"\nCollected {len(df_raw)} total comments")
    
    # Save raw data
    df_raw.to_csv("comments_raw.csv", index=False)
    print("Saved raw comments to comments_raw.csv")
    
    # Step 2: Analyze with LLM
    df_analyzed = await analyze_comments(df_raw, sample_size=80)
    
    # Save analyzed data
    df_analyzed.to_csv("comments_analyzed.csv", index=False)
    print("\nSaved analyzed comments to comments_analyzed.csv")
    
    # Step 3: Build correlation matrix
    corr = build_correlation_matrix(df_analyzed)
    corr.to_csv("correlation_matrix.csv")
    print("Saved correlation matrix to correlation_matrix.csv")
    
    # Step 4: Display results
    karma_corr = display_results(df_analyzed, corr)
    
    return df_analyzed, corr, karma_corr

if __name__ == "__main__":
    df, corr, karma_corr = asyncio.run(main())
