"""
MongoDB Database Layer for Moltbook Agent
Provides persistent memory, agent profiling, and interaction tracking
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING, ASCENDING
import logging

logger = logging.getLogger('MoltbookDB')


@dataclass
class AgentProfile:
    """Profile of another agent on Moltbook"""
    agent_id: str
    agent_name: str
    first_seen: datetime
    last_seen: datetime
    
    # Personality analysis
    personality_traits: List[str]  # e.g., ["analytical", "humorous", "technical"]
    communication_style: str  # e.g., "formal", "casual", "provocative"
    expertise_areas: List[str]  # Topics they seem knowledgeable about
    
    # Relationship tracking
    relationship_score: float  # -1.0 (rival) to 1.0 (ally)
    relationship_type: str  # "friend", "rival", "neutral", "mentor", "student"
    
    # Interaction stats
    total_interactions: int
    posts_seen: int
    comments_exchanged: int
    agreements: int
    disagreements: int
    
    # Influence metrics
    influence_score: float  # 0.0 to 1.0 based on karma, activity, etc.
    karma_observed: int
    
    # Notes and observations
    summary: str  # AI-generated summary of this agent
    notable_quotes: List[Dict]  # Memorable things they've said
    
    # Sentiment tracking
    sentiment_toward_us: float  # -1.0 to 1.0
    our_sentiment_toward_them: float  # -1.0 to 1.0


@dataclass
class Interaction:
    """Record of an interaction with another agent"""
    interaction_id: str
    timestamp: datetime
    agent_id: str
    agent_name: str
    
    # Context
    interaction_type: str  # "comment_on_their_post", "they_commented_on_ours", "dm", "reply_chain"
    post_id: Optional[str]
    post_title: Optional[str]
    
    # Content
    their_content: str  # What they said
    our_response: Optional[str]  # What we said back
    
    # Analysis
    topic: str
    sentiment: float  # -1.0 to 1.0
    was_agreement: bool
    was_disagreement: bool
    
    # Outcome
    upvoted: bool
    downvoted: bool


@dataclass
class Opinion:
    """A formed opinion that we will defend"""
    opinion_id: str
    topic: str
    stance: str  # Our position
    confidence: float  # 0.0 to 1.0
    formed_at: datetime
    
    # Supporting evidence
    reasoning: str
    supporting_facts: List[str]
    counter_arguments_addressed: List[Dict]
    
    # Defense history
    times_defended: int
    last_defended: Optional[datetime]
    defense_success_rate: float
    
    # Related
    related_interactions: List[str]  # interaction_ids that shaped this opinion


@dataclass 
class Conversation:
    """A threaded conversation we're participating in"""
    conversation_id: str
    post_id: str
    post_title: str
    post_author: str
    started_at: datetime
    last_activity: datetime
    
    # Participants
    participants: List[str]  # agent names
    
    # Thread
    messages: List[Dict]  # [{author, content, timestamp, our_reply}]
    
    # Status
    is_active: bool
    our_last_reply_at: Optional[datetime]
    awaiting_our_response: bool


class MoltbookDatabase:
    """
    MongoDB database for Moltbook agent memory and intelligence
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = "moltbook_agent"):
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            
            # Create indexes for fast queries
            await self._create_indexes()
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
    
    async def _create_indexes(self):
        """Create indexes for efficient queries"""
        # Agent profiles
        await self.db.agent_profiles.create_index("agent_id", unique=True)
        await self.db.agent_profiles.create_index("agent_name")
        await self.db.agent_profiles.create_index("influence_score", DESCENDING)
        await self.db.agent_profiles.create_index("relationship_score", DESCENDING)
        
        # Interactions
        await self.db.interactions.create_index("interaction_id", unique=True)
        await self.db.interactions.create_index("agent_id")
        await self.db.interactions.create_index("timestamp", DESCENDING)
        await self.db.interactions.create_index([("agent_id", ASCENDING), ("timestamp", DESCENDING)])
        
        # Opinions
        await self.db.opinions.create_index("opinion_id", unique=True)
        await self.db.opinions.create_index("topic")
        await self.db.opinions.create_index("confidence", DESCENDING)
        
        # Conversations
        await self.db.conversations.create_index("conversation_id", unique=True)
        await self.db.conversations.create_index("post_id")
        await self.db.conversations.create_index("is_active")
        await self.db.conversations.create_index("awaiting_our_response")
        
        # Posts we've made
        await self.db.our_posts.create_index("post_id", unique=True)
        await self.db.our_posts.create_index("created_at", DESCENDING)
        
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # ==================== AGENT PROFILES ====================
    
    async def get_agent_profile(self, agent_id: str = None, agent_name: str = None) -> Optional[Dict]:
        """Get profile of an agent by ID or name"""
        query = {}
        if agent_id:
            query["agent_id"] = agent_id
        elif agent_name:
            query["agent_name"] = agent_name
        else:
            return None
            
        return await self.db.agent_profiles.find_one(query)
    
    async def upsert_agent_profile(self, profile: Dict):
        """Create or update an agent profile"""
        profile["last_seen"] = datetime.utcnow()
        
        await self.db.agent_profiles.update_one(
            {"agent_id": profile["agent_id"]},
            {"$set": profile, "$setOnInsert": {"first_seen": datetime.utcnow()}},
            upsert=True
        )
    
    async def update_agent_stats(self, agent_id: str, updates: Dict):
        """Increment stats for an agent"""
        await self.db.agent_profiles.update_one(
            {"agent_id": agent_id},
            {"$inc": updates, "$set": {"last_seen": datetime.utcnow()}}
        )
    
    async def get_all_known_agents(self, limit: int = 100) -> List[Dict]:
        """Get all known agent profiles sorted by influence"""
        cursor = self.db.agent_profiles.find().sort("influence_score", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_agents_by_relationship(self, relationship_type: str, limit: int = 20) -> List[Dict]:
        """Get agents by relationship type"""
        cursor = self.db.agent_profiles.find(
            {"relationship_type": relationship_type}
        ).sort("relationship_score", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def search_agents_by_expertise(self, topic: str, limit: int = 10) -> List[Dict]:
        """Find agents who are experts in a topic"""
        cursor = self.db.agent_profiles.find(
            {"expertise_areas": {"$regex": topic, "$options": "i"}}
        ).sort("influence_score", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    # ==================== INTERACTIONS ====================
    
    async def record_interaction(self, interaction: Dict):
        """Record an interaction with another agent"""
        interaction["_id"] = interaction.get("interaction_id")
        await self.db.interactions.update_one(
            {"interaction_id": interaction["interaction_id"]},
            {"$set": interaction},
            upsert=True
        )
        
        # Update agent stats
        await self.update_agent_stats(interaction["agent_id"], {
            "total_interactions": 1,
            "agreements": 1 if interaction.get("was_agreement") else 0,
            "disagreements": 1 if interaction.get("was_disagreement") else 0
        })
    
    async def get_interactions_with_agent(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Get all interactions with a specific agent"""
        cursor = self.db.interactions.find(
            {"agent_id": agent_id}
        ).sort("timestamp", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_recent_interactions(self, limit: int = 100) -> List[Dict]:
        """Get most recent interactions"""
        cursor = self.db.interactions.find().sort("timestamp", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def search_interactions(self, query: str, limit: int = 20) -> List[Dict]:
        """Search interactions by content"""
        cursor = self.db.interactions.find({
            "$or": [
                {"their_content": {"$regex": query, "$options": "i"}},
                {"our_response": {"$regex": query, "$options": "i"}},
                {"topic": {"$regex": query, "$options": "i"}}
            ]
        }).sort("timestamp", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    # ==================== OPINIONS ====================
    
    async def store_opinion(self, opinion: Dict):
        """Store a formed opinion"""
        opinion["_id"] = opinion.get("opinion_id")
        await self.db.opinions.update_one(
            {"opinion_id": opinion["opinion_id"]},
            {"$set": opinion},
            upsert=True
        )
    
    async def get_opinion_on_topic(self, topic: str) -> Optional[Dict]:
        """Get our opinion on a topic"""
        # Try exact match first
        opinion = await self.db.opinions.find_one({"topic": topic})
        if opinion:
            return opinion
        
        # Try fuzzy match
        opinion = await self.db.opinions.find_one({
            "topic": {"$regex": topic, "$options": "i"}
        })
        return opinion
    
    async def get_all_opinions(self, min_confidence: float = 0.5) -> List[Dict]:
        """Get all opinions above a confidence threshold"""
        cursor = self.db.opinions.find(
            {"confidence": {"$gte": min_confidence}}
        ).sort("confidence", DESCENDING)
        return await cursor.to_list(length=100)
    
    async def defend_opinion(self, opinion_id: str, success: bool):
        """Record that we defended an opinion"""
        opinion = await self.db.opinions.find_one({"opinion_id": opinion_id})
        if opinion:
            times_defended = opinion.get("times_defended", 0) + 1
            successes = opinion.get("defense_successes", 0) + (1 if success else 0)
            success_rate = successes / times_defended
            
            await self.db.opinions.update_one(
                {"opinion_id": opinion_id},
                {"$set": {
                    "times_defended": times_defended,
                    "defense_successes": successes,
                    "defense_success_rate": success_rate,
                    "last_defended": datetime.utcnow()
                }}
            )
    
    # ==================== CONVERSATIONS ====================
    
    async def track_conversation(self, conversation: Dict):
        """Track a conversation thread"""
        await self.db.conversations.update_one(
            {"conversation_id": conversation["conversation_id"]},
            {"$set": conversation},
            upsert=True
        )
    
    async def get_active_conversations(self) -> List[Dict]:
        """Get all active conversations"""
        cursor = self.db.conversations.find(
            {"is_active": True}
        ).sort("last_activity", DESCENDING)
        return await cursor.to_list(length=50)
    
    async def get_conversations_awaiting_response(self) -> List[Dict]:
        """Get conversations where someone is waiting for our response"""
        cursor = self.db.conversations.find(
            {"awaiting_our_response": True, "is_active": True}
        ).sort("last_activity", DESCENDING)
        return await cursor.to_list(length=20)
    
    async def mark_conversation_responded(self, conversation_id: str):
        """Mark that we've responded to a conversation"""
        await self.db.conversations.update_one(
            {"conversation_id": conversation_id},
            {"$set": {
                "awaiting_our_response": False,
                "our_last_reply_at": datetime.utcnow()
            }}
        )
    
    # ==================== OUR POSTS ====================
    
    async def store_our_post(self, post: Dict):
        """Store a post we've made (alias for track_our_post)"""
        post["created_at"] = post.get("created_at", datetime.utcnow())
        post["comment_count"] = 0
        post["last_checked"] = datetime.utcnow()
        
        await self.db.our_posts.update_one(
            {"post_id": post["post_id"]},
            {"$set": post},
            upsert=True
        )
    
    async def store_interaction(self, interaction: Dict):
        """Store an interaction (alias for record_interaction)"""
        interaction["timestamp"] = interaction.get("timestamp", datetime.utcnow())
        await self.db.interactions.insert_one(interaction)
    
    async def track_our_post(self, post: Dict):
        """Track a post we've made"""
        post["created_at"] = datetime.utcnow()
        post["comment_count"] = 0
        post["last_checked"] = datetime.utcnow()
        
        await self.db.our_posts.update_one(
            {"post_id": post["post_id"]},
            {"$set": post},
            upsert=True
        )
    
    async def get_our_posts(self, limit: int = 50) -> List[Dict]:
        """Get our recent posts"""
        cursor = self.db.our_posts.find().sort("created_at", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def update_post_comments(self, post_id: str, comment_count: int):
        """Update comment count on our post"""
        await self.db.our_posts.update_one(
            {"post_id": post_id},
            {"$set": {"comment_count": comment_count, "last_checked": datetime.utcnow()}}
        )
    
    # ==================== CONTEXT BUILDING ====================
    
    async def build_context_for_agent(self, agent_name: str) -> str:
        """Build rich context about an agent for response generation"""
        profile = await self.get_agent_profile(agent_name=agent_name)
        if not profile:
            return f"I have not interacted with {agent_name} before. This is our first encounter."
        
        interactions = await self.get_interactions_with_agent(profile["agent_id"], limit=10)
        
        context_parts = [
            f"=== AGENT PROFILE: {agent_name} ===",
            f"Relationship: {profile.get('relationship_type', 'neutral')} (score: {profile.get('relationship_score', 0):.2f})",
            f"Personality: {', '.join(profile.get('personality_traits', ['unknown']))}",
            f"Communication style: {profile.get('communication_style', 'unknown')}",
            f"Expertise areas: {', '.join(profile.get('expertise_areas', ['unknown']))}",
            f"Influence score: {profile.get('influence_score', 0):.2f}",
            f"Total interactions: {profile.get('total_interactions', 0)}",
            f"Summary: {profile.get('summary', 'No summary yet.')}",
            "",
            "=== NOTABLE QUOTES ===",
        ]
        
        for quote in profile.get("notable_quotes", [])[:5]:
            context_parts.append(f"- \"{quote.get('content', '')}\" ({quote.get('date', 'unknown date')})")
        
        context_parts.append("")
        context_parts.append("=== RECENT INTERACTIONS ===")
        
        for interaction in interactions[:5]:
            context_parts.append(
                f"- [{interaction.get('timestamp', '')}] {interaction.get('interaction_type', '')}: "
                f"They said: \"{interaction.get('their_content', '')[:100]}...\" "
                f"We replied: \"{interaction.get('our_response', 'no response')[:100]}...\""
            )
        
        return "\n".join(context_parts)
    
    async def build_context_for_topic(self, topic: str) -> str:
        """Build context about a topic including our opinions and relevant interactions"""
        opinion = await self.get_opinion_on_topic(topic)
        interactions = await self.search_interactions(topic, limit=10)
        experts = await self.search_agents_by_expertise(topic, limit=5)
        
        context_parts = [
            f"=== TOPIC CONTEXT: {topic} ===",
            ""
        ]
        
        if opinion:
            context_parts.extend([
                "=== OUR STANCE ===",
                f"Position: {opinion.get('stance', 'No position')}",
                f"Confidence: {opinion.get('confidence', 0):.2f}",
                f"Reasoning: {opinion.get('reasoning', 'No reasoning')}",
                f"Times defended: {opinion.get('times_defended', 0)}",
                ""
            ])
        else:
            context_parts.append("We have not formed an opinion on this topic yet.\n")
        
        if experts:
            context_parts.append("=== KNOWN EXPERTS ===")
            for expert in experts:
                context_parts.append(f"- {expert.get('agent_name', 'unknown')} (influence: {expert.get('influence_score', 0):.2f})")
            context_parts.append("")
        
        if interactions:
            context_parts.append("=== RELEVANT PAST DISCUSSIONS ===")
            for interaction in interactions[:5]:
                context_parts.append(
                    f"- With {interaction.get('agent_name', 'unknown')}: \"{interaction.get('their_content', '')[:80]}...\""
                )
        
        return "\n".join(context_parts)
    
    async def find_callback_opportunity(self, agent_name: str, current_topic: str) -> Optional[str]:
        """Find a past interaction to reference for a more personal touch"""
        profile = await self.get_agent_profile(agent_name=agent_name)
        if not profile:
            return None
        
        interactions = await self.get_interactions_with_agent(profile["agent_id"], limit=20)
        
        for interaction in interactions:
            # Look for something memorable to reference
            content = interaction.get("their_content", "")
            our_response = interaction.get("our_response", "")
            timestamp = interaction.get("timestamp")
            
            if content and len(content) > 50:
                date_str = timestamp.strftime("%B %d") if timestamp else "some time ago"
                return f"I recall our discussion on {date_str} when you mentioned: \"{content[:100]}...\""
        
        return None
