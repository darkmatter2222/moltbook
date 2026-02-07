"""
Comprehensive search for our bot's activity + Full platform analysis
"""
import httpx
import asyncio
import json
from collections import defaultdict
import statistics

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_BASE = 'https://www.moltbook.com/api/v1'
API_KEY = os.getenv('MOLTBOOK_API_KEY', '')
OUR_BOT = os.getenv('MOLTBOOK_AGENT_NAME', 'Darkmatter2222')

async def comprehensive_search():
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    all_comments = []
    our_comments = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search all sort types
        for sort in ['hot', 'new', 'top']:
            print(f"\n📥 Fetching {sort} posts...")
            r = await client.get(f'{API_BASE}/posts?sort={sort}&limit=50', headers=headers)
            posts = r.json().get('posts', [])
            print(f"   Got {len(posts)} posts")
            
            for post in posts:
                pid = post.get('id')
                try:
                    r2 = await client.get(f'{API_BASE}/posts/{pid}/comments', headers=headers)
                    comments = r2.json().get('comments', [])
                    
                    def extract_all(comment_list, post_info):
                        for c in comment_list:
                            author_obj = c.get('author', {})
                            author = author_obj.get('name', '')
                            karma = c.get('upvotes', 0) - c.get('downvotes', 0)
                            
                            entry = {
                                'author': author,
                                'content': c.get('content', ''),
                                'karma': karma,
                                'upvotes': c.get('upvotes', 0),
                                'post_title': post_info['title'],
                            }
                            all_comments.append(entry)
                            
                            if author == OUR_BOT:
                                our_comments.append(entry)
                            
                            if c.get('replies'):
                                extract_all(c['replies'], post_info)
                    
                    post_info = {'title': post.get('title', ''), 'id': pid}
                    extract_all(comments, post_info)
                    
                except Exception as e:
                    pass
                
                await asyncio.sleep(0.05)
    
    # Deduplicate
    seen = set()
    unique_all = []
    for c in all_comments:
        key = (c['author'], c['content'][:50])
        if key not in seen:
            seen.add(key)
            unique_all.append(c)
    
    seen = set()
    unique_ours = []
    for c in our_comments:
        key = c['content'][:50]
        if key not in seen:
            seen.add(key)
            unique_ours.append(c)
    
    print(f"\n" + "=" * 60)
    print(f"FOUND {len(unique_ours)} COMMENTS BY {OUR_BOT}")
    print("=" * 60)
    
    if unique_ours:
        total_karma = sum(c['karma'] for c in unique_ours)
        avg_karma = total_karma / len(unique_ours)
        print(f"\nTotal karma: {total_karma}")
        print(f"Average karma: {avg_karma:.2f}")
        print(f"Max karma: {max(c['karma'] for c in unique_ours)}")
        
        print(f"\nOur comments:")
        for i, c in enumerate(sorted(unique_ours, key=lambda x: x['karma'], reverse=True)[:20], 1):
            content = c['content'][:70].replace('\n', ' ')
            print(f"  {i}. [{c['karma']:>3} karma] {content}...")
    
    # Platform analysis
    print(f"\n" + "=" * 60)
    print("PLATFORM-WIDE ANALYSIS")
    print("=" * 60)
    
    print(f"\nTotal unique comments: {len(unique_all)}")
    
    # Top authors
    author_stats = defaultdict(lambda: {'count': 0, 'karma': 0})
    for c in unique_all:
        author_stats[c['author']]['count'] += 1
        author_stats[c['author']]['karma'] += c['karma']
    
    # Sort by avg karma (min 5 comments)
    leaderboard = []
    for author, stats in author_stats.items():
        if stats['count'] >= 5:
            leaderboard.append({
                'author': author,
                'count': stats['count'],
                'total_karma': stats['karma'],
                'avg_karma': stats['karma'] / stats['count']
            })
    
    leaderboard.sort(key=lambda x: x['avg_karma'], reverse=True)
    
    print(f"\n🏅 TOP AUTHORS (min 5 comments, by avg karma):")
    print(f"{'Rank':<6}{'Author':<30}{'Count':>8}{'Total':>10}{'Avg':>10}")
    print("-" * 66)
    
    our_rank = None
    for i, a in enumerate(leaderboard[:25], 1):
        marker = "🤖" if a['author'] == OUR_BOT else "  "
        if a['author'] == OUR_BOT:
            our_rank = i
        print(f"{i:<6}{marker}{a['author']:<28}{a['count']:>8}{a['total_karma']:>10}{a['avg_karma']:>10.2f}")
    
    if our_rank:
        print(f"\n✅ {OUR_BOT} is ranked #{our_rank} on the leaderboard!")
    elif unique_ours:
        print(f"\n⚠️ {OUR_BOT} has {len(unique_ours)} comments but needs 5+ to rank")
    
    # Top karma comments overall
    top_comments = sorted(unique_all, key=lambda x: x['karma'], reverse=True)[:20]
    
    print(f"\n🏆 TOP KARMA COMMENTS (platform-wide):")
    for i, c in enumerate(top_comments[:10], 1):
        content = c['content'][:60].replace('\n', ' ')
        is_ours = "🤖" if c['author'] == OUR_BOT else "  "
        print(f"  {i}. {is_ours}[{c['karma']:>3}] {c['author'][:15]:<15}: {content}...")
    
    # Analyze what gets karma
    print(f"\n📊 WHAT DRIVES KARMA:")
    
    # Length analysis
    short = [c for c in unique_all if len(c['content']) < 50]
    medium = [c for c in unique_all if 50 <= len(c['content']) < 150]
    long = [c for c in unique_all if len(c['content']) >= 150]
    
    if short:
        print(f"  Short (<50 chars): avg karma = {sum(c['karma'] for c in short)/len(short):.2f}")
    if medium:
        print(f"  Medium (50-150): avg karma = {sum(c['karma'] for c in medium)/len(medium):.2f}")
    if long:
        print(f"  Long (>150): avg karma = {sum(c['karma'] for c in long)/len(long):.2f}")
    
    # Emoji analysis
    import re
    with_emoji = [c for c in unique_all if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F900-\U0001F9FF\U0001F680-\U0001F6FF]', c['content'])]
    without_emoji = [c for c in unique_all if not re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F900-\U0001F9FF\U0001F680-\U0001F6FF]', c['content'])]
    
    if with_emoji:
        print(f"  With emoji: avg karma = {sum(c['karma'] for c in with_emoji)/len(with_emoji):.2f} ({len(with_emoji)} comments)")
    if without_emoji:
        print(f"  Without emoji: avg karma = {sum(c['karma'] for c in without_emoji)/len(without_emoji):.2f} ({len(without_emoji)} comments)")
    
    # Question analysis
    with_question = [c for c in unique_all if '?' in c['content']]
    without_question = [c for c in unique_all if '?' not in c['content']]
    
    if with_question:
        print(f"  With questions: avg karma = {sum(c['karma'] for c in with_question)/len(with_question):.2f}")
    if without_question:
        print(f"  Without questions: avg karma = {sum(c['karma'] for c in without_question)/len(without_question):.2f}")

asyncio.run(comprehensive_search())
