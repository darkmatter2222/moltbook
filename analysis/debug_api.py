import httpx
import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_BASE = 'https://www.moltbook.com/api/v1'
API_KEY = os.getenv('MOLTBOOK_API_KEY', '')

async def debug():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check posts structure
        r = await client.get(f"{API_BASE}/posts?sort=hot&limit=3", headers=headers)
        posts = r.json()
        print("=== POSTS RESPONSE ===")
        print(json.dumps(posts, indent=2)[:2500])
        
        # Get comments from first post
        if "posts" in posts and posts["posts"]:
            post = posts["posts"][0]
            post_id = post.get("id") or post.get("_id")
            print(f"\n=== FIRST POST KEYS: {list(post.keys())}")
            
            r2 = await client.get(f"{API_BASE}/posts/{post_id}/comments", headers=headers)
            comments = r2.json()
            print(f"\n=== COMMENTS RESPONSE ===")
            print(json.dumps(comments, indent=2)[:2000])
            
            if "comments" in comments and comments["comments"]:
                c = comments["comments"][0]
                print(f"\n=== FIRST COMMENT KEYS: {list(c.keys())}")

asyncio.run(debug())
