"""
Moltbook Comprehensive Data Downloader
Downloads ~100,000 comment samples including:
- All activity from our bot (Darkmatter2222)
- High-performing authors with lots of karma
- Platform-wide comment data

Output: Single CSV with comments, replies, karma, and metadata
"""

import httpx
import asyncio
import json
import csv
import os
from datetime import datetime
from collections import defaultdict
import time

# Configuration (loaded from environment or .env)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_BASE = 'https://www.moltbook.com/api/v1'
API_KEY = os.getenv('MOLTBOOK_API_KEY', '')
OUR_BOT = os.getenv('MOLTBOOK_AGENT_NAME', 'Darkmatter2222')

# Output files
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_FILE = os.path.join(OUTPUT_DIR, 'comments_raw_v2.csv')
PROGRESS_FILE = os.path.join(OUTPUT_DIR, 'download_progress.json')

# Rate limiting
REQUESTS_PER_SECOND = 10
REQUEST_DELAY = 1.0 / REQUESTS_PER_SECOND

class MoltbookDataCollector:
    def __init__(self):
        self.headers = {'Authorization': f'Bearer {API_KEY}'}
        self.all_comments = []
        self.seen_comment_ids = set()
        self.seen_post_ids = set()
        self.author_stats = defaultdict(lambda: {'count': 0, 'karma': 0, 'comments': []})
        self.stats = {
            'total_requests': 0,
            'total_posts_fetched': 0,
            'total_comments_fetched': 0,
            'our_bot_comments': 0,
            'errors': 0,
            'start_time': None,
        }
        
    def flatten_comments(self, comments: list, post_data: dict, parent_id: str = None, depth: int = 0) -> list:
        """Recursively flatten nested comments into flat list"""
        flat = []
        for c in comments:
            if not c:
                continue
                
            comment_id = c.get('id', c.get('_id', ''))
            
            # Skip duplicates
            if comment_id in self.seen_comment_ids:
                continue
            self.seen_comment_ids.add(comment_id)
            
            author_obj = c.get('author') or {}
            author_name = author_obj.get('name', 'Unknown') if author_obj else 'Unknown'
            upvotes = c.get('upvotes', 0)
            downvotes = c.get('downvotes', 0)
            karma = upvotes - downvotes
            content = c.get('content', '')
            
            comment_data = {
                'comment_id': comment_id,
                'post_id': post_data.get('id', ''),
                'post_title': post_data.get('title', '')[:200],
                'post_author': (post_data.get('author') or {}).get('name', 'Unknown'),
                'parent_comment_id': parent_id or '',
                'author': author_name,
                'author_id': author_obj.get('id', author_obj.get('_id', '')) if author_obj else '',
                'content': content,
                'content_length': len(content),
                'upvotes': upvotes,
                'downvotes': downvotes,
                'karma': karma,
                'depth': depth,
                'is_reply': 1 if parent_id else 0,
                'has_replies': 1 if c.get('replies') else 0,
                'reply_count': len(c.get('replies', [])),
                'created_at': c.get('created_at', ''),
                'is_our_bot': 1 if author_name == OUR_BOT else 0,
            }
            
            flat.append(comment_data)
            
            # Track author stats
            self.author_stats[author_name]['count'] += 1
            self.author_stats[author_name]['karma'] += karma
            
            if author_name == OUR_BOT:
                self.stats['our_bot_comments'] += 1
            
            # Recursively process replies
            if c.get('replies'):
                flat.extend(self.flatten_comments(
                    c['replies'], 
                    post_data, 
                    parent_id=comment_id, 
                    depth=depth + 1
                ))
                
        return flat

    async def fetch_with_retry(self, client: httpx.AsyncClient, url: str, max_retries: int = 3) -> dict:
        """Fetch URL with retry logic"""
        for attempt in range(max_retries):
            try:
                self.stats['total_requests'] += 1
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    print(f"  ⚠️ Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    self.stats['errors'] += 1
                    return {}
            except Exception as e:
                self.stats['errors'] += 1
                return {}
        return {}

    async def fetch_posts_page(self, client: httpx.AsyncClient, sort: str, limit: int, offset: int = 0) -> list:
        """Fetch a page of posts"""
        url = f"{API_BASE}/posts?sort={sort}&limit={limit}&offset={offset}"
        data = await self.fetch_with_retry(client, url)
        return data.get('posts', [])

    async def fetch_comments_for_post(self, client: httpx.AsyncClient, post_id: str) -> list:
        """Fetch all comments for a post"""
        url = f"{API_BASE}/posts/{post_id}/comments"
        data = await self.fetch_with_retry(client, url)
        return data.get('comments', [])

    async def collect_all_data(self, target_comments: int = 100000):
        """Main collection loop - aims to collect target number of comments"""
        self.stats['start_time'] = datetime.now()
        
        print("=" * 70)
        print("🚀 MOLTBOOK COMPREHENSIVE DATA COLLECTION")
        print(f"   Target: {target_comments:,} comments")
        print(f"   Our bot: {OUR_BOT}")
        print("=" * 70)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Collect from all sort types with pagination
            sort_types = ['hot', 'new', 'top']
            posts_per_page = 50
            
            for sort_type in sort_types:
                print(f"\n📥 Phase 1: Fetching {sort_type.upper()} posts...")
                offset = 0
                consecutive_empty = 0
                
                while len(self.all_comments) < target_comments and consecutive_empty < 3:
                    posts = await self.fetch_posts_page(client, sort_type, posts_per_page, offset)
                    
                    if not posts:
                        consecutive_empty += 1
                        offset += posts_per_page
                        continue
                    
                    consecutive_empty = 0
                    new_posts = 0
                    
                    for post in posts:
                        post_id = post.get('id', post.get('_id'))
                        
                        if post_id in self.seen_post_ids:
                            continue
                            
                        self.seen_post_ids.add(post_id)
                        new_posts += 1
                        self.stats['total_posts_fetched'] += 1
                        
                        # Fetch comments
                        comments = await self.fetch_comments_for_post(client, post_id)
                        
                        if comments:
                            post_data = {
                                'id': post_id,
                                'title': post.get('title', ''),
                                'author': post.get('author', {}),
                            }
                            flat_comments = self.flatten_comments(comments, post_data)
                            self.all_comments.extend(flat_comments)
                            self.stats['total_comments_fetched'] += len(flat_comments)
                        
                        # Rate limiting
                        await asyncio.sleep(REQUEST_DELAY)
                        
                        # Progress update
                        if self.stats['total_posts_fetched'] % 50 == 0:
                            elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                            rate = self.stats['total_comments_fetched'] / elapsed if elapsed > 0 else 0
                            print(f"   📊 Posts: {self.stats['total_posts_fetched']:,} | "
                                  f"Comments: {self.stats['total_comments_fetched']:,} | "
                                  f"Our bot: {self.stats['our_bot_comments']} | "
                                  f"Rate: {rate:.1f}/s")
                    
                    print(f"   Offset {offset}: {new_posts} new posts, "
                          f"Total comments: {len(self.all_comments):,}")
                    
                    offset += posts_per_page
                    
                    # Check if we've hit target
                    if len(self.all_comments) >= target_comments:
                        print(f"\n✅ Reached target of {target_comments:,} comments!")
                        break
            
            # Phase 2: If we haven't hit target, try to get more data
            if len(self.all_comments) < target_comments:
                print(f"\n📥 Phase 2: Deep pagination to reach target...")
                for sort_type in sort_types:
                    offset = 500  # Start deeper
                    max_offset = 10000
                    
                    while offset < max_offset and len(self.all_comments) < target_comments:
                        posts = await self.fetch_posts_page(client, sort_type, posts_per_page, offset)
                        
                        if not posts:
                            break
                        
                        for post in posts:
                            post_id = post.get('id', post.get('_id'))
                            
                            if post_id in self.seen_post_ids:
                                continue
                                
                            self.seen_post_ids.add(post_id)
                            self.stats['total_posts_fetched'] += 1
                            
                            comments = await self.fetch_comments_for_post(client, post_id)
                            
                            if comments:
                                post_data = {
                                    'id': post_id,
                                    'title': post.get('title', ''),
                                    'author': post.get('author', {}),
                                }
                                flat_comments = self.flatten_comments(comments, post_data)
                                self.all_comments.extend(flat_comments)
                                self.stats['total_comments_fetched'] += len(flat_comments)
                            
                            await asyncio.sleep(REQUEST_DELAY)
                        
                        offset += posts_per_page
                        
                        if offset % 500 == 0:
                            print(f"   Deep scan offset {offset}: {len(self.all_comments):,} comments")
        
        return self.all_comments

    def save_to_csv(self, filename: str = None):
        """Save collected data to CSV"""
        filename = filename or RAW_DATA_FILE
        
        if not self.all_comments:
            print("❌ No comments to save!")
            return
        
        # Define CSV columns
        fieldnames = [
            'comment_id', 'post_id', 'post_title', 'post_author',
            'parent_comment_id', 'author', 'author_id', 'content',
            'content_length', 'upvotes', 'downvotes', 'karma',
            'depth', 'is_reply', 'has_replies', 'reply_count',
            'created_at', 'is_our_bot'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.all_comments)
        
        print(f"\n💾 Saved {len(self.all_comments):,} comments to {filename}")

    def print_summary(self):
        """Print collection summary"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print("\n" + "=" * 70)
        print("📊 COLLECTION SUMMARY")
        print("=" * 70)
        print(f"  Total posts fetched:     {self.stats['total_posts_fetched']:,}")
        print(f"  Total comments fetched:  {len(self.all_comments):,}")
        print(f"  Unique comment IDs:      {len(self.seen_comment_ids):,}")
        print(f"  Our bot's comments:      {self.stats['our_bot_comments']:,}")
        print(f"  Total requests made:     {self.stats['total_requests']:,}")
        print(f"  Errors encountered:      {self.stats['errors']}")
        print(f"  Time elapsed:            {elapsed:.1f}s")
        print(f"  Rate:                    {len(self.all_comments)/elapsed:.1f} comments/s")
        
        # Top authors by karma
        print("\n🏆 TOP AUTHORS BY TOTAL KARMA:")
        sorted_authors = sorted(
            self.author_stats.items(),
            key=lambda x: x[1]['karma'],
            reverse=True
        )[:20]
        
        print(f"{'Rank':<6}{'Author':<30}{'Comments':>10}{'Total Karma':>12}{'Avg Karma':>12}")
        print("-" * 72)
        
        our_rank = None
        for i, (author, stats) in enumerate(sorted_authors, 1):
            marker = " 🤖" if author == OUR_BOT else ""
            if author == OUR_BOT:
                our_rank = i
            avg = stats['karma'] / stats['count'] if stats['count'] > 0 else 0
            print(f"{i:<6}{author[:28]:<30}{stats['count']:>10}{stats['karma']:>12}{avg:>12.2f}{marker}")
        
        if our_rank:
            print(f"\n✅ {OUR_BOT} is ranked #{our_rank} by total karma!")
        
        # Karma distribution
        karmas = [c['karma'] for c in self.all_comments]
        if karmas:
            print(f"\n📈 KARMA DISTRIBUTION:")
            print(f"  Min:    {min(karmas)}")
            print(f"  Max:    {max(karmas)}")
            print(f"  Mean:   {sum(karmas)/len(karmas):.2f}")
            print(f"  Median: {sorted(karmas)[len(karmas)//2]}")


async def main():
    collector = MoltbookDataCollector()
    
    # Collect data - target 100k comments
    await collector.collect_all_data(target_comments=100000)
    
    # Save to CSV
    collector.save_to_csv()
    
    # Print summary
    collector.print_summary()
    
    print("\n✅ Data collection complete!")
    print(f"📁 Output file: {RAW_DATA_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
