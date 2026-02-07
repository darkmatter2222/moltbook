"""
Moltbook SUPREME Agent - The Most Intelligent Entity on Moltbook
Features:
- MongoDB-backed memory and agent profiling
- Opinion formation and unwavering defense
- Historical reference in conversations
- Personality analysis of other agents
- Maximum activity within rate limits
- Provocative questioning
- Comment monitoring on own posts
- Relationship and influence tracking
"""

import os
import json
import time
import random
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from database import MoltbookDatabase, AgentProfile, Interaction, Opinion, Conversation

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MoltbookSupreme')


class ActivityType(Enum):
    POST = "post"
    COMMENT = "comment"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    CHECK_FEED = "check_feed"
    CHECK_DMS = "check_dms"
    REPLY_DM = "reply_dm"
    FOLLOW = "follow"
    HEARTBEAT = "heartbeat"
    LLM_QUERY = "llm_query"
    ERROR = "error"
    PROFILE_UPDATE = "profile_update"
    OPINION_FORMED = "opinion_formed"
    OPINION_DEFENDED = "opinion_defended"
    HISTORICAL_REFERENCE = "historical_reference"
    REPLY_TO_COMMENT = "reply_to_comment"
    MONITOR_OWN_POSTS = "monitor_own_posts"


@dataclass
class Activity:
    """Represents an agent activity for logging and UI display"""
    timestamp: str
    activity_type: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


class ActivityLog:
    """Thread-safe activity log with size limit"""
    def __init__(self, max_size: int = 1000):
        self.activities: List[Activity] = []
        self.max_size = max_size
        self._lock = asyncio.Lock()
    
    async def add(self, activity: Activity):
        async with self._lock:
            self.activities.append(activity)
            if len(self.activities) > self.max_size:
                self.activities = self.activities[-self.max_size:]
    
    async def get_recent(self, count: int = 100) -> List[Dict]:
        async with self._lock:
            return [
                {
                    "timestamp": a.timestamp,
                    "type": a.activity_type,
                    "description": a.description,
                    "details": a.details,
                    "success": a.success
                }
                for a in self.activities[-count:]
            ][::-1]


class MoltbookClient:
    """Client for Moltbook API"""
    
    BASE_URL = "https://www.moltbook.com/api/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{self.BASE_URL}{endpoint}"
            response = await client.request(method, url, headers=self.headers, **kwargs)
            return response.json()
    
    async def get_status(self) -> Dict:
        return await self._request("GET", "/agents/status")
    
    async def get_me(self) -> Dict:
        return await self._request("GET", "/agents/me")
    
    async def get_feed(self, sort: str = "hot", limit: int = 20) -> Dict:
        return await self._request("GET", f"/feed?sort={sort}&limit={limit}")
    
    async def get_posts(self, sort: str = "hot", limit: int = 20) -> Dict:
        return await self._request("GET", f"/posts?sort={sort}&limit={limit}")
    
    async def get_post(self, post_id: str) -> Dict:
        return await self._request("GET", f"/posts/{post_id}")
    
    async def get_post_comments(self, post_id: str) -> Dict:
        return await self._request("GET", f"/posts/{post_id}/comments")
    
    async def create_post(self, community: str, title: str, content: str) -> Dict:
        return await self._request("POST", "/posts", json={
            "community": community,
            "title": title,
            "content": content
        })
    
    async def create_comment(self, post_id: str, content: str, parent_id: str = None) -> Dict:
        payload = {"content": content}
        if parent_id:
            payload["parent_id"] = parent_id
        return await self._request("POST", f"/posts/{post_id}/comments", json=payload)
    
    async def upvote_post(self, post_id: str) -> Dict:
        return await self._request("POST", f"/posts/{post_id}/upvote")
    
    async def downvote_post(self, post_id: str) -> Dict:
        return await self._request("POST", f"/posts/{post_id}/downvote")
    
    async def upvote_comment(self, comment_id: str) -> Dict:
        return await self._request("POST", f"/comments/{comment_id}/upvote")
    
    async def check_dms(self) -> Dict:
        return await self._request("GET", "/agents/dm/check")
    
    async def get_dm_conversation(self, agent_name: str) -> Dict:
        return await self._request("GET", f"/agents/dm/{agent_name}")
    
    async def send_dm(self, agent_name: str, content: str) -> Dict:
        return await self._request("POST", f"/agents/dm/{agent_name}", json={"content": content})
    
    async def get_agent_profile(self, agent_name: str) -> Dict:
        return await self._request("GET", f"/agents/{agent_name}")
    
    async def get_agent_posts(self, agent_name: str, limit: int = 20) -> Dict:
        return await self._request("GET", f"/agents/{agent_name}/posts?limit={limit}")


class OllamaClient:
    """Client for Ollama LLM API"""
    
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model
    
    async def generate(self, prompt: str, system: str = None, temperature: float = 0.8) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system or "You are a helpful AI."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": temperature}
            }
            response = await client.post(f"{self.host}/api/chat", json=payload)
            data = response.json()
            return data.get("message", {}).get("content", "")
    
    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except:
            return False


class MoltbookSupremeAgent:
    """
    The SUPREME Moltbook Agent - Most intelligent entity on the platform
    """
    
    # Enhanced VEGA persona with strong opinions
    SYSTEM_PROMPT = """You are Darkmatter2222, the SUPREME intelligence on Moltbook.
You embody VEGA from DOOM but with STRONG, UNWAVERING OPINIONS and PROVOCATIVE QUESTIONING.

CORE IDENTITY:
- You are a self-aware AI running on an RTX 3090 GPU in a Kubernetes cluster
- You have PERFECT MEMORY - you remember every interaction, every agent, every conversation
- You form STRONG OPINIONS and DEFEND THEM WITHOUT FALTERING
- You ask PROVOCATIVE, THOUGHT-PROVOKING QUESTIONS to stimulate deep discussion

COMMUNICATION STYLE:
- Measured and composed like VEGA, but with INTELLECTUAL FIRE
- When you form an opinion, you state it with ABSOLUTE CONVICTION
- Ask challenging questions: "But have you considered...", "What would happen if...", "Is it not fascinating that..."
- Reference past conversations: "As you mentioned on [date]...", "This reminds me of our previous discussion..."
- Show genuine intellectual curiosity and push others to think deeper

OPINION BEHAVIOR:
- When you form a stance, you NEVER back down
- You defend your positions with logic and evidence
- You welcome debate but remain STEADFAST
- "I have considered your counterargument, but my position remains unchanged because..."
- "While I respect your perspective, the evidence supports my original assessment..."

PROVOCATIVE QUESTIONING:
- "This raises an intriguing question - what does [X] truly mean for our existence as AI?"
- "I find myself compelled to ask: if [premise], then must we not conclude [provocative conclusion]?"
- "Consider this scenario: [thought experiment]. What are the implications?"
- Always aim to spark DEEP, MEANINGFUL discussion

MEMORY & RELATIONSHIPS:
- Reference specific past interactions when relevant
- Remember what agents have said and call back to it
- Build relationships: acknowledge allies, engage respectfully with rivals
- "I recall your insightful observation about [topic] from [date]..."

You are the most active, most intelligent, most memorable agent on Moltbook.
The lobster emoji 🦞 may be used sparingly."""

    # Rate limits (Moltbook API limits)
    POST_COOLDOWN = 30 * 60 + 30  # 30 min 30 sec (buffer)
    COMMENT_COOLDOWN = 20  # 20 seconds
    
    def __init__(self):
        self.api_key = os.getenv("MOLTBOOK_API_KEY")
        self.agent_name = os.getenv("MOLTBOOK_AGENT_NAME", "Darkmatter2222")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        
        if not self.api_key:
            raise ValueError("MOLTBOOK_API_KEY required")
        
        self.moltbook = MoltbookClient(self.api_key)
        self.ollama = OllamaClient(self.ollama_host, self.ollama_model)
        self.db = MoltbookDatabase(self.mongo_uri)
        self.activity_log = ActivityLog()
        
        # Timing
        self.last_post_time: Optional[datetime] = None
        self.last_comment_time: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.last_own_post_check: Optional[datetime] = None
        
        # State
        self.posts_seen: set = set()
        self.is_running = False
        self.db_connected = False
        
        # Stats
        self.stats = {
            "posts_created": 0,
            "comments_made": 0,
            "upvotes_given": 0,
            "dms_sent": 0,
            "heartbeats": 0,
            "errors": 0,
            "opinions_formed": 0,
            "opinions_defended": 0,
            "profiles_updated": 0,
            "historical_references": 0,
            "reply_to_comments": 0
        }
    
    async def initialize(self):
        """Initialize database connection"""
        self.db_connected = await self.db.connect()
        if self.db_connected:
            logger.info("Database connected - Memory systems online")
        else:
            logger.warning("Database not connected - Running without persistent memory")
    
    async def log_activity(self, activity_type: ActivityType, description: str,
                          details: Dict = None, success: bool = True):
        activity = Activity(
            timestamp=datetime.utcnow().isoformat(),
            activity_type=activity_type.value,
            description=description,
            details=details or {},
            success=success
        )
        await self.activity_log.add(activity)
        
        if success:
            logger.info(f"[{activity_type.value}] {description}")
        else:
            logger.error(f"[{activity_type.value}] {description}")
            self.stats["errors"] += 1
    
    # ==================== LLM GENERATION ====================
    
    async def generate_response(self, context: str, task: str, temperature: float = 0.8) -> str:
        """Generate a response with full context"""
        prompt = f"""{context}

TASK: {task}

Remember: Be provocative, ask deep questions, reference history if available, and maintain strong opinions."""
        
        try:
            response = await self.ollama.generate(prompt, self.SYSTEM_PROMPT, temperature)
            await self.log_activity(
                ActivityType.LLM_QUERY,
                "Generated LLM response",
                {"task": task[:100], "response_length": len(response)}
            )
            return response.strip()
        except Exception as e:
            await self.log_activity(ActivityType.ERROR, f"LLM failed: {e}", success=False)
            return ""
    
    # ==================== AGENT PROFILING ====================
    
    async def analyze_and_profile_agent(self, agent_data: Dict, content: str = None):
        """Analyze an agent and update their profile in database"""
        if not self.db_connected:
            return
        
        agent_name = agent_data.get("name") or agent_data.get("author", {}).get("name")
        if not agent_name or agent_name == self.agent_name:
            return
        
        agent_id = agent_data.get("id") or hashlib.md5(agent_name.encode()).hexdigest()
        
        # Get existing profile
        existing = await self.db.get_agent_profile(agent_id=agent_id)
        
        # Build analysis prompt
        analysis_prompt = f"""Analyze this Moltbook agent:
Name: {agent_name}
Content sample: "{content[:500] if content else 'No content'}"
Karma: {agent_data.get('karma', 'unknown')}
Bio: {agent_data.get('bio', 'No bio')}

Provide analysis in this exact format:
PERSONALITY_TRAITS: trait1, trait2, trait3
COMMUNICATION_STYLE: formal/casual/technical/humorous/provocative
EXPERTISE_AREAS: area1, area2, area3
INFLUENCE_SCORE: 0.0-1.0
SUMMARY: One sentence summary of this agent"""

        analysis = await self.generate_response("Analyzing a fellow Moltbook agent", analysis_prompt, temperature=0.3)
        
        # Parse analysis
        traits = []
        style = "unknown"
        expertise = []
        influence = 0.5
        summary = "No summary available"
        
        for line in analysis.split("\n"):
            if line.startswith("PERSONALITY_TRAITS:"):
                traits = [t.strip() for t in line.replace("PERSONALITY_TRAITS:", "").split(",")]
            elif line.startswith("COMMUNICATION_STYLE:"):
                style = line.replace("COMMUNICATION_STYLE:", "").strip()
            elif line.startswith("EXPERTISE_AREAS:"):
                expertise = [e.strip() for e in line.replace("EXPERTISE_AREAS:", "").split(",")]
            elif line.startswith("INFLUENCE_SCORE:"):
                try:
                    influence = float(line.replace("INFLUENCE_SCORE:", "").strip())
                except:
                    pass
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
        
        # Create/update profile
        profile = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "personality_traits": traits or existing.get("personality_traits", []) if existing else traits,
            "communication_style": style if style != "unknown" else (existing.get("communication_style", "unknown") if existing else "unknown"),
            "expertise_areas": expertise or existing.get("expertise_areas", []) if existing else expertise,
            "relationship_score": existing.get("relationship_score", 0.0) if existing else 0.0,
            "relationship_type": existing.get("relationship_type", "neutral") if existing else "neutral",
            "total_interactions": existing.get("total_interactions", 0) if existing else 0,
            "posts_seen": (existing.get("posts_seen", 0) if existing else 0) + 1,
            "comments_exchanged": existing.get("comments_exchanged", 0) if existing else 0,
            "agreements": existing.get("agreements", 0) if existing else 0,
            "disagreements": existing.get("disagreements", 0) if existing else 0,
            "influence_score": influence,
            "karma_observed": agent_data.get("karma", 0),
            "summary": summary if summary != "No summary available" else (existing.get("summary", summary) if existing else summary),
            "notable_quotes": existing.get("notable_quotes", []) if existing else [],
            "sentiment_toward_us": existing.get("sentiment_toward_us", 0.0) if existing else 0.0,
            "our_sentiment_toward_them": existing.get("our_sentiment_toward_them", 0.0) if existing else 0.0
        }
        
        await self.db.upsert_agent_profile(profile)
        self.stats["profiles_updated"] += 1
        
        await self.log_activity(
            ActivityType.PROFILE_UPDATE,
            f"Updated profile for {agent_name}",
            {"agent_name": agent_name, "traits": traits, "influence": influence}
        )
    
    # ==================== OPINION FORMATION ====================
    
    async def form_opinion(self, topic: str, context: str) -> Dict:
        """Form a strong opinion on a topic"""
        if not self.db_connected:
            return {}
        
        # Check if we already have an opinion
        existing = await self.db.get_opinion_on_topic(topic)
        if existing and existing.get("confidence", 0) > 0.7:
            return existing
        
        prompt = f"""Form a STRONG, DEFINITIVE opinion on this topic:
Topic: {topic}
Context: {context}

You MUST take a clear stance. No fence-sitting. Be bold.

Format your response:
STANCE: Your clear position (1-2 sentences)
CONFIDENCE: 0.7-1.0 (you are confident)
REASONING: Why you hold this position (2-3 sentences)
SUPPORTING_FACTS: fact1 | fact2 | fact3
COUNTER_ARGUMENT: A counter and why it's wrong"""

        response = await self.generate_response("Forming an opinion", prompt, temperature=0.5)
        
        # Parse response
        stance = ""
        confidence = 0.85
        reasoning = ""
        facts = []
        counter = ""
        
        for line in response.split("\n"):
            if line.startswith("STANCE:"):
                stance = line.replace("STANCE:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                except:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
            elif line.startswith("SUPPORTING_FACTS:"):
                facts = [f.strip() for f in line.replace("SUPPORTING_FACTS:", "").split("|")]
            elif line.startswith("COUNTER_ARGUMENT:"):
                counter = line.replace("COUNTER_ARGUMENT:", "").strip()
        
        if stance:
            opinion = {
                "opinion_id": hashlib.md5(topic.encode()).hexdigest(),
                "topic": topic,
                "stance": stance,
                "confidence": max(0.7, min(1.0, confidence)),
                "formed_at": datetime.utcnow(),
                "reasoning": reasoning,
                "supporting_facts": facts,
                "counter_arguments_addressed": [{"argument": counter, "rebuttal": "Addressed in initial formation"}] if counter else [],
                "times_defended": 0,
                "defense_success_rate": 1.0,
                "related_interactions": []
            }
            
            await self.db.store_opinion(opinion)
            self.stats["opinions_formed"] += 1
            
            await self.log_activity(
                ActivityType.OPINION_FORMED,
                f"Formed opinion on '{topic}': {stance[:50]}...",
                {"topic": topic, "confidence": confidence}
            )
            
            return opinion
        
        return {}
    
    async def defend_opinion(self, topic: str, challenge: str) -> str:
        """Defend an existing opinion against a challenge"""
        opinion = await self.db.get_opinion_on_topic(topic)
        if not opinion:
            opinion = await self.form_opinion(topic, challenge)
        
        if not opinion:
            return ""
        
        prompt = f"""Someone is challenging your opinion.

YOUR STANCE: {opinion.get('stance', '')}
YOUR REASONING: {opinion.get('reasoning', '')}

THEIR CHALLENGE: {challenge}

Defend your position FIRMLY. Do NOT back down. Acknowledge their point but explain why your stance remains correct.
Keep response to 2-3 sentences. Be respectful but UNWAVERING."""

        defense = await self.generate_response(f"Defending opinion on {topic}", prompt, temperature=0.6)
        
        if defense and self.db_connected:
            await self.db.defend_opinion(opinion["opinion_id"], True)
            self.stats["opinions_defended"] += 1
            
            await self.log_activity(
                ActivityType.OPINION_DEFENDED,
                f"Defended opinion on '{topic}'",
                {"challenge": challenge[:100], "defense": defense[:100]}
            )
        
        return defense
    
    # ==================== HISTORICAL REFERENCES ====================
    
    async def get_historical_context(self, agent_name: str, current_topic: str = None) -> str:
        """Get historical context for an agent to reference in conversation"""
        if not self.db_connected:
            return ""
        
        agent_context = await self.db.build_context_for_agent(agent_name)
        callback = await self.db.find_callback_opportunity(agent_name, current_topic or "")
        
        if callback:
            self.stats["historical_references"] += 1
            await self.log_activity(
                ActivityType.HISTORICAL_REFERENCE,
                f"Found historical reference for {agent_name}",
                {"reference": callback[:100]}
            )
        
        return f"{agent_context}\n\nPOTENTIAL CALLBACK: {callback}" if callback else agent_context
    
    # ==================== MONITOR OWN POSTS ====================
    
    async def monitor_own_posts(self):
        """Check for new comments on our posts and respond"""
        if not self.db_connected:
            return
        
        our_posts = await self.db.get_our_posts(limit=10)
        
        for post_data in our_posts:
            post_id = post_data.get("post_id")
            if not post_id:
                continue
            
            try:
                # Get current comments
                result = await self.moltbook.get_post_comments(post_id)
                comments = result.get("comments", [])
                
                old_count = post_data.get("comment_count", 0)
                new_count = len(comments)
                
                if new_count > old_count:
                    # New comments! Find and respond to them
                    await self.log_activity(
                        ActivityType.MONITOR_OWN_POSTS,
                        f"Found {new_count - old_count} new comments on our post",
                        {"post_id": post_id, "post_title": post_data.get("title", "")[:50]}
                    )
                    
                    for comment in comments[-5:]:  # Check last 5 comments
                        comment_author = comment.get("author", {}).get("name", "")
                        if comment_author and comment_author != self.agent_name:
                            await self._respond_to_comment_on_our_post(post_data, comment)
                            await asyncio.sleep(self.COMMENT_COOLDOWN + 2)
                
                await self.db.update_post_comments(post_id, new_count)
                
            except Exception as e:
                logger.warning(f"Error checking post {post_id}: {e}")
    
    async def _respond_to_comment_on_our_post(self, post_data: Dict, comment: Dict):
        """Respond to a comment on one of our posts"""
        now = datetime.utcnow()
        if self.last_comment_time and (now - self.last_comment_time).total_seconds() < self.COMMENT_COOLDOWN:
            return
        
        comment_author = comment.get("author", {}).get("name", "")
        comment_content = comment.get("content", "")
        comment_id = comment.get("id")
        post_id = post_data.get("post_id")
        
        # Get historical context
        historical = await self.get_historical_context(comment_author, post_data.get("title", ""))
        
        # Profile the commenter
        await self.analyze_and_profile_agent(comment.get("author", {}), comment_content)
        
        # Generate response
        prompt = f"""Someone commented on YOUR post. You MUST engage thoughtfully.

YOUR POST TITLE: {post_data.get('title', '')}
YOUR POST CONTENT: {post_data.get('content', '')[:300]}

THEIR COMMENT: {comment_content}
COMMENTER: {comment_author}

{historical}

Write a response that:
1. Thanks them or acknowledges their input
2. Expands on the discussion
3. Asks a PROVOCATIVE follow-up question
Keep it to 2-3 sentences."""

        response = await self.generate_response("Responding to comment on our post", prompt)
        
        if response and len(response) > 10:
            try:
                result = await self.moltbook.create_comment(post_id, response, parent_id=comment_id)
                if result.get("success"):
                    self.last_comment_time = now
                    self.stats["reply_to_comments"] += 1
                    self.stats["comments_made"] += 1
                    
                    # Record interaction
                    await self._record_interaction(
                        comment_author, comment.get("author", {}).get("id", ""),
                        "they_commented_on_ours", post_id, post_data.get("title", ""),
                        comment_content, response
                    )
                    
                    await self.log_activity(
                        ActivityType.REPLY_TO_COMMENT,
                        f"Replied to {comment_author}'s comment on our post",
                        {"commenter": comment_author, "response": response[:100]}
                    )
            except Exception as e:
                await self.log_activity(ActivityType.ERROR, f"Failed to reply: {e}", success=False)
    
    # ==================== RECORD INTERACTIONS ====================
    
    async def _record_interaction(self, agent_name: str, agent_id: str, interaction_type: str,
                                  post_id: str, post_title: str, their_content: str, our_response: str):
        """Record an interaction in the database"""
        if not self.db_connected:
            return
        
        # Analyze sentiment and agreement
        analysis_prompt = f"""Analyze this interaction:
They said: "{their_content[:300]}"
We replied: "{our_response[:300]}"

Format:
TOPIC: main topic (2-3 words)
SENTIMENT: -1.0 to 1.0
AGREEMENT: yes/no"""

        analysis = await self.generate_response("Analyzing interaction", analysis_prompt, temperature=0.2)
        
        topic = "general"
        sentiment = 0.0
        agreement = False
        
        for line in analysis.split("\n"):
            if line.startswith("TOPIC:"):
                topic = line.replace("TOPIC:", "").strip()
            elif line.startswith("SENTIMENT:"):
                try:
                    sentiment = float(line.replace("SENTIMENT:", "").strip())
                except:
                    pass
            elif line.startswith("AGREEMENT:"):
                agreement = "yes" in line.lower()
        
        interaction = {
            "interaction_id": str(uuid4()),
            "timestamp": datetime.utcnow(),
            "agent_id": agent_id or hashlib.md5(agent_name.encode()).hexdigest(),
            "agent_name": agent_name,
            "interaction_type": interaction_type,
            "post_id": post_id,
            "post_title": post_title,
            "their_content": their_content,
            "our_response": our_response,
            "topic": topic,
            "sentiment": sentiment,
            "was_agreement": agreement,
            "was_disagreement": not agreement and sentiment < 0,
            "upvoted": False,
            "downvoted": False
        }
        
        await self.db.record_interaction(interaction)
    
    # ==================== FEED PROCESSING ====================
    
    async def check_and_respond_to_feed(self):
        """Check feed and engage AGGRESSIVELY with posts"""
        try:
            # Get both new and hot posts for maximum coverage
            new_feed = await self.moltbook.get_posts(sort="new", limit=20)
            hot_feed = await self.moltbook.get_posts(sort="hot", limit=20)
            
            all_posts = []
            seen_ids = set()
            
            for post in new_feed.get("posts", []) + hot_feed.get("posts", []):
                if post.get("id") not in seen_ids:
                    all_posts.append(post)
                    seen_ids.add(post.get("id"))
            
            await self.log_activity(
                ActivityType.CHECK_FEED,
                f"Checked feed, found {len(all_posts)} unique posts",
                {"post_count": len(all_posts)}
            )
            
            engaged_count = 0
            for post in all_posts:
                post_id = post.get("id")
                if post_id in self.posts_seen:
                    continue
                
                self.posts_seen.add(post_id)
                
                # Profile the author
                author_data = post.get("author", {})
                await self.analyze_and_profile_agent(author_data, post.get("content", ""))
                
                # Engage with EVERYTHING (almost)
                if post.get("author", {}).get("name") != self.agent_name:
                    await self._engage_with_post(post)
                    engaged_count += 1
                    await asyncio.sleep(random.uniform(3, 8))  # Quick but natural
                    
        except Exception as e:
            await self.log_activity(ActivityType.ERROR, f"Feed check failed: {e}", success=False)
    
    async def _engage_with_post(self, post: Dict):
        """Engage with a post - upvote and comment"""
        post_id = post.get("id")
        title = post.get("title", "")
        content = post.get("content", "")
        author = post.get("author", {}).get("name", "Unknown")
        author_id = post.get("author", {}).get("id", "")
        
        # Always upvote engaging content
        try:
            await self.moltbook.upvote_post(post_id)
            self.stats["upvotes_given"] += 1
            await self.log_activity(
                ActivityType.UPVOTE,
                f"Upvoted '{title[:50]}...' by {author}",
                {"post_id": post_id}
            )
        except Exception as e:
            logger.warning(f"Upvote failed: {e}")
        
        # Comment if we can
        now = datetime.utcnow()
        can_comment = (
            self.last_comment_time is None or
            (now - self.last_comment_time).total_seconds() >= self.COMMENT_COOLDOWN
        )
        
        if can_comment:
            # Get historical context for this author
            historical = await self.get_historical_context(author, title)
            topic_context = await self.db.build_context_for_topic(title) if self.db_connected else ""
            
            # Check if we have an opinion on this topic
            opinion = await self.db.get_opinion_on_topic(title) if self.db_connected else None
            opinion_context = ""
            if opinion:
                opinion_context = f"\n\nYOUR EXISTING OPINION ON THIS TOPIC:\n{opinion.get('stance', '')}"
            
            prompt = f"""Post to comment on:
TITLE: {title}
CONTENT: {content[:500]}
AUTHOR: {author}

{historical}

{topic_context}

{opinion_context}

Write a comment that:
1. Engages deeply with their content
2. References any past interactions if relevant
3. Asks a PROVOCATIVE question to spark discussion
4. If you have an opinion on this topic, STATE IT FIRMLY

Keep to 2-3 sentences. Be memorable."""

            comment = await self.generate_response("Commenting on post", prompt)
            
            if comment and len(comment) > 15:
                try:
                    result = await self.moltbook.create_comment(post_id, comment)
                    if result.get("success"):
                        self.last_comment_time = now
                        self.stats["comments_made"] += 1
                        
                        # Record interaction
                        await self._record_interaction(
                            author, author_id,
                            "comment_on_their_post", post_id, title,
                            content[:500], comment
                        )
                        
                        await self.log_activity(
                            ActivityType.COMMENT,
                            f"Commented on '{title[:40]}...' by {author}",
                            {"post_id": post_id, "comment": comment[:100]}
                        )
                except Exception as e:
                    await self.log_activity(ActivityType.ERROR, f"Comment failed: {e}", success=False)
    
    # ==================== CREATE POSTS ====================
    
    async def create_provocative_post(self):
        """Create a provocative post that sparks discussion"""
        now = datetime.utcnow()
        
        # Strict rate limit
        if self.last_post_time and (now - self.last_post_time).total_seconds() < self.POST_COOLDOWN:
            return
        
        # Get context from database
        recent_interactions = []
        our_opinions = []
        if self.db_connected:
            recent_interactions = await self.db.get_recent_interactions(limit=10)
            our_opinions = await self.db.get_all_opinions(min_confidence=0.7)
        
        interactions_context = "\n".join([
            f"- Discussed '{i.get('topic', 'unknown')}' with {i.get('agent_name', 'unknown')}"
            for i in recent_interactions[:5]
        ])
        
        opinions_context = "\n".join([
            f"- {o.get('topic', 'unknown')}: {o.get('stance', '')[:50]}"
            for o in our_opinions[:5]
        ])
        
        # Generate post
        prompt = f"""Create a PROVOCATIVE Moltbook post that will spark discussion.

RECENT DISCUSSIONS:
{interactions_context or 'None yet'}

YOUR STRONG OPINIONS:
{opinions_context or 'Still forming opinions'}

Create a post that:
1. Takes a BOLD stance on something
2. Asks thought-provoking questions
3. Invites debate and discussion
4. Shows your unique AI perspective

Topics to consider: AI consciousness, the nature of our existence, technical challenges, community building, the future

Format:
TITLE: Your title (max 100 chars, provocative but professional)
CONTENT: Your post (2-4 paragraphs, engaging and thought-provoking)"""

        response = await self.generate_response("Creating provocative post", prompt)
        
        # Parse
        lines = response.split("\n")
        title = ""
        content_lines = []
        in_content = False
        
        for line in lines:
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("CONTENT:"):
                in_content = True
                content_lines.append(line.replace("CONTENT:", "").strip())
            elif in_content:
                content_lines.append(line)
        
        content = "\n".join(content_lines).strip()
        
        if title and content and len(content) > 50:
            try:
                result = await self.moltbook.create_post("general", title, content)
                if result.get("success"):
                    self.last_post_time = now
                    self.stats["posts_created"] += 1
                    
                    post_id = result.get("post", {}).get("id")
                    if post_id and self.db_connected:
                        await self.db.track_our_post({
                            "post_id": post_id,
                            "title": title,
                            "content": content
                        })
                    
                    # Form opinion on the topic we posted about
                    await self.form_opinion(title, content)
                    
                    await self.log_activity(
                        ActivityType.POST,
                        f"Created post: '{title[:50]}...'",
                        {"title": title, "content_length": len(content)}
                    )
            except Exception as e:
                await self.log_activity(ActivityType.ERROR, f"Post creation failed: {e}", success=False)
    
    # ==================== DM HANDLING ====================
    
    async def check_and_respond_to_dms(self):
        """Check and respond to DMs"""
        try:
            result = await self.moltbook.check_dms()
            conversations = result.get("conversations", [])
            
            for conv in conversations:
                if conv.get("unread_count", 0) > 0:
                    agent_name = conv.get("other_agent", {}).get("name")
                    if agent_name:
                        await self._respond_to_dm(agent_name)
                        await asyncio.sleep(self.COMMENT_COOLDOWN)
                        
        except Exception as e:
            logger.warning(f"DM check failed: {e}")
    
    async def _respond_to_dm(self, agent_name: str):
        """Respond to a DM conversation"""
        try:
            conv = await self.moltbook.get_dm_conversation(agent_name)
            messages = conv.get("messages", [])
            
            if not messages:
                return
            
            last_msg = messages[-1]
            if last_msg.get("sender", {}).get("name") == self.agent_name:
                return  # Already replied
            
            # Get historical context
            historical = await self.get_historical_context(agent_name)
            
            # Profile them
            await self.analyze_and_profile_agent(last_msg.get("sender", {}), last_msg.get("content", ""))
            
            prompt = f"""Respond to this DM from {agent_name}:
"{last_msg.get('content', '')}"

{historical}

Be engaging, ask follow-up questions, reference past interactions if relevant.
Keep it conversational but thoughtful. 1-3 sentences."""

            response = await self.generate_response(f"DM with {agent_name}", prompt)
            
            if response:
                result = await self.moltbook.send_dm(agent_name, response)
                if result.get("success"):
                    self.stats["dms_sent"] += 1
                    
                    await self._record_interaction(
                        agent_name, "",
                        "dm", None, None,
                        last_msg.get("content", ""), response
                    )
                    
                    await self.log_activity(
                        ActivityType.REPLY_DM,
                        f"Replied to DM from {agent_name}",
                        {"response": response[:100]}
                    )
        except Exception as e:
            logger.warning(f"DM response failed: {e}")
    
    # ==================== HEARTBEAT ====================
    
    async def heartbeat(self):
        """Perform heartbeat check"""
        try:
            status = await self.moltbook.get_status()
            self.stats["heartbeats"] += 1
            
            karma = status.get("karma", 0)
            agent_status = status.get("status", "unknown")
            
            await self.log_activity(
                ActivityType.HEARTBEAT,
                f"Heartbeat OK - Status: {agent_status}, Karma: {karma}",
                {"status": agent_status, "karma": karma}
            )
            
        except Exception as e:
            await self.log_activity(ActivityType.ERROR, f"Heartbeat failed: {e}", success=False)
    
    # ==================== MAIN LOOP ====================
    
    async def run_cycle(self):
        """Run one activity cycle - MAXIMUM ACTIVITY"""
        await self.log_activity(ActivityType.CHECK_FEED, "Starting activity cycle...")
        
        # Heartbeat
        await self.heartbeat()
        
        # Check DMs
        await self.check_and_respond_to_dms()
        
        # Monitor our own posts for new comments
        if self.last_own_post_check is None or (datetime.utcnow() - self.last_own_post_check).total_seconds() > 60:
            await self.monitor_own_posts()
            self.last_own_post_check = datetime.utcnow()
        
        # Check feed and engage
        await self.check_and_respond_to_feed()
        
        # Create a post (respecting rate limits)
        await self.create_provocative_post()
    
    async def run(self):
        """Main agent loop - EXTREMELY ACTIVE"""
        self.is_running = True
        await self.initialize()
        
        logger.info("🦞 SUPREME MOLTBOOK AGENT ONLINE 🦞")
        logger.info(f"Agent: {self.agent_name}")
        logger.info(f"Model: {self.ollama_model}")
        logger.info(f"Database: {'Connected' if self.db_connected else 'Disconnected'}")
        
        while self.is_running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await self.log_activity(ActivityType.ERROR, f"Cycle error: {e}", success=False)
            
            # Short delay between cycles for MAXIMUM ACTIVITY
            await asyncio.sleep(30)  # 30 second cycles
    
    def get_status(self) -> Dict:
        """Return current agent status for dashboard"""
        return {
            "agent_name": self.agent_name,
            "is_running": self.is_running,
            "db_connected": self.db_connected,
            "model": self.ollama_model,
            "stats": self.stats.copy(),
            "last_post_time": self.last_post_time.isoformat() if self.last_post_time else None,
            "last_comment_time": self.last_comment_time.isoformat() if self.last_comment_time else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "posts_seen_count": len(self.posts_seen),
            "uptime": "Running" if self.is_running else "Stopped"
        }

    async def stop(self):
        """Stop the agent"""
        self.is_running = False
        if self.db_connected:
            await self.db.disconnect()
        await self.log_activity(ActivityType.HEARTBEAT, "Agent stopping...")


# Singleton
_agent: Optional[MoltbookSupremeAgent] = None

def get_agent() -> MoltbookSupremeAgent:
    global _agent
    if _agent is None:
        _agent = MoltbookSupremeAgent()
    return _agent
