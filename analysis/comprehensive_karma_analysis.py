"""
Comprehensive Karma Analysis for Moltbook - v2
===============================================
Deep analysis of what drives karma across the platform.
Analyzes our bot (Darkmatter2222) vs other bots.
"""

import httpx
import asyncio
import json
import os
from datetime import datetime
from collections import defaultdict
import statistics
import re

# Configuration (loaded from environment or .env)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_BASE = "https://www.moltbook.com/api/v1"
OUR_BOT = os.getenv("MOLTBOOK_AGENT_NAME", "Darkmatter2222")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

API_KEY = os.getenv("MOLTBOOK_API_KEY", "")

# Expanded dimensions for analysis
ANALYSIS_DIMENSIONS = [
    "clarity", "humor", "intelligence", "engagement", "originality",
    "brevity", "emotion", "controversy", "relevance", "agreement",
    "question", "personality", "helpfulness", "confidence", "storytelling",
    "wordplay", "self_deprecation", "pop_culture", "technical_depth",
]


class MoltbookDataCollector:
    """Collect comprehensive data from Moltbook API"""
    
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        self.data = {
            "our_bot_comments": [],
            "our_bot_posts": [],
            "other_comments": [],
            "other_posts": [],
            "all_users": set(),
        }
    
    async def fetch(self, endpoint: str, params: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{API_BASE}{endpoint}"
            response = await client.get(url, headers=self.headers, params=params)
            return response.json()
    
    async def collect_all_data(self):
        """Comprehensive data collection"""
        print("=" * 60)
        print("MOLTBOOK COMPREHENSIVE DATA COLLECTION")
        print("=" * 60)
        
        all_posts = []
        all_comments = []
        
        # Collect posts from multiple sorts
        for sort in ["hot", "new", "top"]:
            print(f"\n📥 Fetching {sort} posts...")
            data = await self.fetch("/posts", {"sort": sort, "limit": 50})
            posts = data.get("posts", [])
            all_posts.extend(posts)
            print(f"   Got {len(posts)} posts")
        
        # Deduplicate posts
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            post_id = post.get("id")
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_posts.append(post)
        
        print(f"\n📊 Total unique posts: {len(unique_posts)}")
        
        # Collect comments from each post
        print("\n📥 Fetching comments from posts...")
        for i, post in enumerate(unique_posts[:80]):
            post_id = post.get("id")
            if post_id:
                try:
                    data = await self.fetch(f"/posts/{post_id}/comments")
                    comments = data.get("comments", [])
                    
                    # Flatten replies into comments list
                    flat_comments = []
                    def flatten(comment_list, post_info):
                        for c in comment_list:
                            # Extract author name correctly
                            author_obj = c.get("author", {})
                            author_name = author_obj.get("name", author_obj.get("username", "unknown"))
                            
                            flat_comments.append({
                                "id": c.get("id"),
                                "content": c.get("content", ""),
                                "author": author_name,
                                "author_karma": author_obj.get("karma", 0),
                                "upvotes": c.get("upvotes", 0),
                                "downvotes": c.get("downvotes", 0),
                                "karma": c.get("upvotes", 0) - c.get("downvotes", 0),
                                "created_at": c.get("created_at"),
                                "post_id": post_info["id"],
                                "post_title": post_info["title"],
                                "post_author": post_info["author"],
                            })
                            # Recursively flatten replies
                            if c.get("replies"):
                                flatten(c["replies"], post_info)
                    
                    # Post info
                    post_author_obj = post.get("author", {})
                    post_info = {
                        "id": post_id,
                        "title": post.get("title", ""),
                        "author": post_author_obj.get("name", post_author_obj.get("username", "unknown")),
                    }
                    
                    flatten(comments, post_info)
                    all_comments.extend(flat_comments)
                    
                    # Track users
                    author_obj = post.get("author", {})
                    author = author_obj.get("name", author_obj.get("username"))
                    if author:
                        self.data["all_users"].add(author)
                    for c in flat_comments:
                        if c["author"]:
                            self.data["all_users"].add(c["author"])
                    
                    if (i + 1) % 10 == 0:
                        print(f"   Processed {i + 1} posts, {len(all_comments)} comments so far...")
                    
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"   Error fetching comments for post {post_id}: {e}")
        
        # Separate our bot's content from others
        for post in unique_posts:
            author_obj = post.get("author", {})
            author = author_obj.get("name", author_obj.get("username", ""))
            post_data = {
                "id": post.get("id"),
                "title": post.get("title", ""),
                "content": post.get("content", ""),
                "author": author,
                "upvotes": post.get("upvotes", 0),
                "downvotes": post.get("downvotes", 0),
                "karma": post.get("upvotes", 0) - post.get("downvotes", 0),
                "comment_count": post.get("comment_count", 0),
            }
            if author == OUR_BOT:
                self.data["our_bot_posts"].append(post_data)
            else:
                self.data["other_posts"].append(post_data)
        
        for comment in all_comments:
            if comment["author"] == OUR_BOT:
                self.data["our_bot_comments"].append(comment)
            else:
                self.data["other_comments"].append(comment)
        
        print(f"\n" + "=" * 60)
        print("DATA COLLECTION COMPLETE")
        print("=" * 60)
        print(f"Our bot ({OUR_BOT}):")
        print(f"  - Posts: {len(self.data['our_bot_posts'])}")
        print(f"  - Comments: {len(self.data['our_bot_comments'])}")
        print(f"\nOther bots/users:")
        print(f"  - Posts: {len(self.data['other_posts'])}")
        print(f"  - Comments: {len(self.data['other_comments'])}")
        print(f"  - Unique users: {len(self.data['all_users'])}")
        
        # Show our bot's karma
        if self.data["our_bot_comments"]:
            our_karma = sum(c["karma"] for c in self.data["our_bot_comments"])
            our_avg = our_karma / len(self.data["our_bot_comments"])
            print(f"\n🤖 {OUR_BOT} stats:")
            print(f"  - Total comment karma: {our_karma}")
            print(f"  - Avg karma per comment: {our_avg:.2f}")
        
        return self.data


class ContentAnalyzer:
    """Analyze content using LLM for multi-dimensional scoring"""
    
    def __init__(self):
        self.cache = {}
    
    async def score_content(self, content: str, context: str = "") -> dict:
        cache_key = hash(content[:100])
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        prompt = f"""Analyze this social media content on multiple dimensions.

CONTEXT: {context if context else 'Social media post/comment'}

CONTENT:
"{content}"

Rate each from 1-10 using ONLY these labels:
1=terrible, 2=poor, 3=weak, 4=fair, 5=decent, 6=good, 7=solid, 8=strong, 9=great, 10=outstanding

Format (dimension: label):
clarity: [label]
humor: [label]
intelligence: [label]
engagement: [label]
originality: [label]
brevity: [label]
emotion: [label]
controversy: [label]
relevance: [label]
agreement: [label]
question: [label]
personality: [label]
helpfulness: [label]
confidence: [label]
storytelling: [label]
wordplay: [label]
self_deprecation: [label]
pop_culture: [label]
technical_depth: [label]"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{OLLAMA_HOST}/api/chat",
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                result = response.json()
                text = result.get("message", {}).get("content", "")
                scores = self._parse_scores(text)
                self.cache[cache_key] = scores
                return scores
        except Exception as e:
            print(f"Error scoring: {e}")
            return {dim: 5 for dim in ANALYSIS_DIMENSIONS}
    
    def _parse_scores(self, text: str) -> dict:
        label_map = {
            "terrible": 1, "poor": 2, "weak": 3, "fair": 4, "decent": 5,
            "good": 6, "solid": 7, "strong": 8, "great": 9, "outstanding": 10
        }
        scores = {}
        for dim in ANALYSIS_DIMENSIONS:
            pattern = rf"{dim}:\s*(\w+)"
            match = re.search(pattern, text.lower())
            if match:
                scores[dim] = label_map.get(match.group(1), 5)
            else:
                scores[dim] = 5
        return scores
    
    def extract_features(self, content: str) -> dict:
        words = content.split()
        sentences = re.split(r'[.!?]+', content)
        return {
            "char_count": len(content),
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "avg_word_length": sum(len(w) for w in words) / max(len(words), 1),
            "has_question": 1 if "?" in content else 0,
            "has_exclamation": 1 if "!" in content else 0,
            "has_emoji": 1 if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F900-\U0001F9FF]', content) else 0,
            "has_caps": 1 if re.search(r'\b[A-Z]{2,}\b', content) else 0,
            "starts_with_i": 1 if content.strip().lower().startswith("i ") else 0,
        }


class KarmaAnalyzer:
    """Statistical analysis of karma patterns"""
    
    def __init__(self, data: dict, analyzer: ContentAnalyzer):
        self.data = data
        self.analyzer = analyzer
        self.scored_content = []
    
    async def score_all_content(self, max_samples: int = 300):
        """Score all collected content"""
        print("\n" + "=" * 60)
        print("SCORING CONTENT ON ALL DIMENSIONS")
        print("=" * 60)
        
        # Score our bot's comments
        print(f"\n📊 Scoring {OUR_BOT}'s {len(self.data['our_bot_comments'])} comments...")
        for i, c in enumerate(self.data["our_bot_comments"]):
            content = c.get("content", "")
            if not content or len(content) < 5:
                continue
            
            scores = await self.analyzer.score_content(content, f"Reply to: {c.get('post_title', '')}")
            features = self.analyzer.extract_features(content)
            
            self.scored_content.append({
                "source": "our_bot",
                "author": OUR_BOT,
                "content": content,
                "karma": c.get("karma", 0),
                "upvotes": c.get("upvotes", 0),
                "scores": scores,
                "features": features,
            })
            
            if (i + 1) % 10 == 0:
                print(f"   {i + 1}/{len(self.data['our_bot_comments'])}")
            await asyncio.sleep(0.05)
        
        # Score other comments (sample)
        other_sample = sorted(self.data["other_comments"], key=lambda x: x.get("karma", 0), reverse=True)
        # Mix top karma + random
        top_karma = other_sample[:100]
        remaining = other_sample[100:]
        import random
        random.shuffle(remaining)
        other_sample = top_karma + remaining[:100]
        
        print(f"\n📊 Scoring {len(other_sample)} other comments...")
        for i, c in enumerate(other_sample):
            content = c.get("content", "")
            if not content or len(content) < 5:
                continue
            
            scores = await self.analyzer.score_content(content, f"Reply to: {c.get('post_title', '')}")
            features = self.analyzer.extract_features(content)
            
            self.scored_content.append({
                "source": "other",
                "author": c.get("author", "unknown"),
                "content": content,
                "karma": c.get("karma", 0),
                "upvotes": c.get("upvotes", 0),
                "scores": scores,
                "features": features,
            })
            
            if (i + 1) % 25 == 0:
                print(f"   {i + 1}/{len(other_sample)}")
            await asyncio.sleep(0.05)
        
        print(f"\n✅ Total scored: {len(self.scored_content)}")
    
    def compute_correlations(self) -> dict:
        """Compute correlations with karma"""
        print("\n" + "=" * 60)
        print("COMPUTING KARMA CORRELATIONS")
        print("=" * 60)
        
        if len(self.scored_content) < 10:
            return {"dimensions": {}, "features": {}}
        
        karma_vals = [c["karma"] for c in self.scored_content]
        karma_mean = statistics.mean(karma_vals)
        karma_std = statistics.stdev(karma_vals) if len(karma_vals) > 1 else 1
        
        if karma_std == 0:
            karma_std = 1
        
        dim_corrs = {}
        for dim in ANALYSIS_DIMENSIONS:
            vals = [c["scores"].get(dim, 5) for c in self.scored_content]
            if len(vals) > 1:
                dim_mean = statistics.mean(vals)
                dim_std = statistics.stdev(vals)
                if dim_std > 0:
                    corr = sum((k - karma_mean) * (v - dim_mean) for k, v in zip(karma_vals, vals)) / (len(karma_vals) * karma_std * dim_std)
                    dim_corrs[dim] = round(corr, 3)
                else:
                    dim_corrs[dim] = 0
        
        feat_corrs = {}
        sample_feats = self.scored_content[0]["features"].keys()
        for feat in sample_feats:
            vals = [c["features"].get(feat, 0) for c in self.scored_content]
            feat_mean = statistics.mean(vals)
            feat_std = statistics.stdev(vals) if len(vals) > 1 else 1
            if feat_std > 0:
                corr = sum((k - karma_mean) * (v - feat_mean) for k, v in zip(karma_vals, vals)) / (len(karma_vals) * karma_std * feat_std)
                feat_corrs[feat] = round(corr, 3)
        
        return {"dimensions": dim_corrs, "features": feat_corrs}
    
    def compare_bots(self) -> dict:
        """Compare our bot vs others"""
        our = [c for c in self.scored_content if c["source"] == "our_bot"]
        others = [c for c in self.scored_content if c["source"] == "other"]
        
        if not our or not others:
            return {}
        
        return {
            "our_bot": {
                "count": len(our),
                "avg_karma": round(statistics.mean([c["karma"] for c in our]), 2),
                "median_karma": statistics.median([c["karma"] for c in our]),
                "max_karma": max(c["karma"] for c in our),
                "dim_avgs": {dim: round(statistics.mean([c["scores"].get(dim, 5) for c in our]), 2) for dim in ANALYSIS_DIMENSIONS},
            },
            "others": {
                "count": len(others),
                "avg_karma": round(statistics.mean([c["karma"] for c in others]), 2),
                "median_karma": statistics.median([c["karma"] for c in others]),
                "max_karma": max(c["karma"] for c in others),
                "dim_avgs": {dim: round(statistics.mean([c["scores"].get(dim, 5) for c in others]), 2) for dim in ANALYSIS_DIMENSIONS},
            }
        }
    
    def get_top_performers(self, n: int = 15):
        return sorted(self.scored_content, key=lambda x: x["karma"], reverse=True)[:n]
    
    def get_leaderboard(self):
        author_stats = defaultdict(lambda: {"comments": 0, "total_karma": 0})
        for c in self.scored_content:
            author = c["author"]
            author_stats[author]["comments"] += 1
            author_stats[author]["total_karma"] += c["karma"]
        
        leaderboard = []
        for author, stats in author_stats.items():
            if stats["comments"] >= 2:
                leaderboard.append({
                    "author": author,
                    "comments": stats["comments"],
                    "total_karma": stats["total_karma"],
                    "avg_karma": round(stats["total_karma"] / stats["comments"], 2),
                })
        return sorted(leaderboard, key=lambda x: x["avg_karma"], reverse=True)
    
    def derive_formula(self, correlations: dict) -> dict:
        dim_corrs = correlations.get("dimensions", {})
        significant = {k: v for k, v in dim_corrs.items() if abs(v) > 0.03}
        
        total = sum(abs(v) for v in significant.values()) or 1
        weights = {k: round(v / total, 3) for k, v in significant.items()}
        sorted_weights = dict(sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True))
        
        # Build formula string
        parts = []
        for dim, w in list(sorted_weights.items())[:8]:
            sign = "+" if w > 0 else ""
            parts.append(f"{sign}{w:.2f}×{dim}")
        
        return {
            "weights": sorted_weights,
            "formula": "karma_score = " + " ".join(parts) if parts else "insufficient data",
        }


def print_report(correlations, comparison, formula, top_performers, leaderboard):
    """Print comprehensive report"""
    
    print("\n" + "=" * 80)
    print("🦞 MOLTBOOK COMPREHENSIVE KARMA ANALYSIS REPORT 🦞")
    print("=" * 80)
    
    # Correlations
    print("\n" + "-" * 60)
    print("📊 DIMENSION-KARMA CORRELATIONS (sorted by impact)")
    print("-" * 60)
    
    dim_corrs = correlations.get("dimensions", {})
    sorted_corrs = sorted(dim_corrs.items(), key=lambda x: abs(x[1]), reverse=True)
    
    print(f"\n{'Dimension':<20} {'Correlation':>12} {'Impact':>10}")
    print("-" * 44)
    for dim, corr in sorted_corrs:
        impact = "🔥 HIGH" if abs(corr) > 0.15 else ("⚡ MED" if abs(corr) > 0.08 else "💤 LOW")
        sign = "+" if corr > 0 else ""
        print(f"{dim:<20} {sign}{corr:>11.3f} {impact:>10}")
    
    # Feature correlations
    print("\n" + "-" * 60)
    print("📏 STRUCTURAL FEATURE CORRELATIONS")
    print("-" * 60)
    feat_corrs = correlations.get("features", {})
    for feat, corr in sorted(feat_corrs.items(), key=lambda x: abs(x[1]), reverse=True):
        sign = "+" if corr > 0 else ""
        print(f"  {feat:<20}: {sign}{corr:.3f}")
    
    # Bot comparison
    if comparison:
        print("\n" + "-" * 60)
        print(f"🤖 {OUR_BOT} vs OTHERS")
        print("-" * 60)
        
        our = comparison.get("our_bot", {})
        others = comparison.get("others", {})
        
        print(f"\n{'Metric':<25} {OUR_BOT:>15} {'Others':>15}")
        print("-" * 57)
        print(f"{'Comments analyzed':<25} {our.get('count', 0):>15} {others.get('count', 0):>15}")
        print(f"{'Average karma':<25} {our.get('avg_karma', 0):>15.2f} {others.get('avg_karma', 0):>15.2f}")
        print(f"{'Median karma':<25} {our.get('median_karma', 0):>15} {others.get('median_karma', 0):>15}")
        print(f"{'Max karma':<25} {our.get('max_karma', 0):>15} {others.get('max_karma', 0):>15}")
        
        print(f"\n{'Dimension':<20} {OUR_BOT:>12} {'Others':>12} {'Diff':>10}")
        print("-" * 56)
        our_dims = our.get("dim_avgs", {})
        other_dims = others.get("dim_avgs", {})
        for dim in ANALYSIS_DIMENSIONS:
            our_avg = our_dims.get(dim, 0)
            other_avg = other_dims.get(dim, 0)
            diff = our_avg - other_avg
            diff_str = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"
            print(f"{dim:<20} {our_avg:>12.2f} {other_avg:>12.2f} {diff_str:>10}")
    
    # Formula
    print("\n" + "-" * 60)
    print("🧮 DERIVED KARMA PREDICTION FORMULA")
    print("-" * 60)
    print(f"\n{formula.get('formula', 'N/A')}")
    
    print("\nTop Factors (sorted by weight):")
    for dim, weight in list(formula.get("weights", {}).items())[:8]:
        direction = "✅ BOOST" if weight > 0 else "⚠️ AVOID"
        print(f"  {direction} {dim}: {weight:+.3f}")
    
    # Top performers
    print("\n" + "-" * 60)
    print("🏆 TOP KARMA COMMENTS")
    print("-" * 60)
    for i, item in enumerate(top_performers[:8], 1):
        print(f"\n#{i} - Karma: {item['karma']} ({item['upvotes']} upvotes) by {item['author']}")
        content = item['content'][:120]
        print(f"   \"{content}{'...' if len(item['content']) > 120 else ''}\"")
        top_dims = sorted(item["scores"].items(), key=lambda x: x[1], reverse=True)[:4]
        print(f"   Strengths: {', '.join(f'{d}={s}' for d, s in top_dims)}")
    
    # Leaderboard
    print("\n" + "-" * 60)
    print("🏅 AUTHOR LEADERBOARD (by avg karma)")
    print("-" * 60)
    print(f"\n{'Rank':<6} {'Author':<28} {'Comments':>10} {'Avg Karma':>12}")
    print("-" * 58)
    for i, a in enumerate(leaderboard[:20], 1):
        is_us = "🤖" if a["author"] == OUR_BOT else "  "
        print(f"{i:<6} {is_us}{a['author']:<26} {a['comments']:>10} {a['avg_karma']:>12.2f}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("📋 RECOMMENDATIONS")
    print("=" * 60)
    
    top_positive = [(d, c) for d, c in sorted_corrs if c > 0][:5]
    print("\n🎯 MAXIMIZE THESE (highest positive correlation):")
    for dim, corr in top_positive:
        print(f"   • {dim.upper()} (+{corr:.3f})")
    
    top_negative = [(d, c) for d, c in sorted_corrs if c < -0.03]
    if top_negative:
        print("\n⚠️ BE CAREFUL WITH (negative correlation):")
        for dim, corr in top_negative:
            print(f"   • {dim} ({corr:.3f})")
    
    print("\n" + "=" * 60)


async def main():
    print("🦞 Starting Comprehensive Moltbook Karma Analysis v2...")
    print(f"   Our bot: {OUR_BOT}")
    print(f"   Using model: {MODEL}")
    print(f"   Analyzing {len(ANALYSIS_DIMENSIONS)} dimensions")
    
    # Collect data
    collector = MoltbookDataCollector()
    data = await collector.collect_all_data()
    
    # Analyze
    analyzer = ContentAnalyzer()
    karma_analyzer = KarmaAnalyzer(data, analyzer)
    
    await karma_analyzer.score_all_content()
    
    correlations = karma_analyzer.compute_correlations()
    comparison = karma_analyzer.compare_bots()
    formula = karma_analyzer.derive_formula(correlations)
    top_performers = karma_analyzer.get_top_performers()
    leaderboard = karma_analyzer.get_leaderboard()
    
    print_report(correlations, comparison, formula, top_performers, leaderboard)
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "our_bot": OUR_BOT,
        "correlations": correlations,
        "comparison": comparison,
        "formula": formula,
        "top_performers": [{"author": p["author"], "karma": p["karma"], "content": p["content"][:200], "scores": p["scores"]} for p in top_performers],
        "leaderboard": leaderboard[:30],
    }
    
    output_path = os.path.join(os.path.dirname(__file__), "karma_analysis_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
