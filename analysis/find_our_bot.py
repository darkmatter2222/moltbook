import httpx
import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

async def find_our_comments():
    headers = {'Authorization': f'Bearer {os.getenv("MOLTBOOK_API_KEY", "")}'}
    our_bot = 'Darkmatter2222'
    found = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check new posts for our comments
        r = await client.get('https://www.moltbook.com/api/v1/posts?sort=new&limit=50', headers=headers)
        posts = r.json().get('posts', [])
        
        print(f"Checking {len(posts)} posts for comments by {our_bot}...")
        
        for post in posts:
            pid = post.get('id')
            r2 = await client.get(f'https://www.moltbook.com/api/v1/posts/{pid}/comments', headers=headers)
            comments = r2.json().get('comments', [])
            
            def check_comments(comment_list, depth=0):
                for c in comment_list:
                    author = c.get('author', {}).get('name', '')
                    if author == our_bot:
                        found.append({
                            'post': post.get('title', '')[:50],
                            'comment': c.get('content', ''),
                            'karma': c.get('upvotes', 0) - c.get('downvotes', 0),
                            'upvotes': c.get('upvotes', 0),
                        })
                    # Recursively check replies
                    if c.get('replies'):
                        check_comments(c['replies'], depth + 1)
            
            check_comments(comments)
    
    print(f"\n=== Found {len(found)} comments by {our_bot} ===\n")
    
    if found:
        total_karma = sum(f['karma'] for f in found)
        avg_karma = total_karma / len(found)
        print(f"Total karma: {total_karma}")
        print(f"Avg karma: {avg_karma:.2f}")
        print(f"\nRecent comments:")
        for i, f in enumerate(found[:15], 1):
            content = f['comment'][:80].replace('\n', ' ')
            print(f"  {i}. [{f['karma']} karma] {content}...")
    else:
        print("No comments found - checking if the bot has been active recently...")
        
asyncio.run(find_our_comments())
