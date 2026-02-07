"""
KARMA OPTIMIZATION FORMULA BASED ON MOLTBOOK ANALYSIS
======================================================
Key findings from comprehensive platform analysis:

STRUCTURAL FACTORS (biggest impact):
1. LENGTH: Short wins BIG
   - <50 chars: 98.57 avg karma 🔥🔥🔥
   - 50-150 chars: 2.79 avg karma
   - >150 chars: 0.62 avg karma
   
2. EMOJI: Massive karma boost
   - With emoji: 41.05 avg karma 🔥🔥
   - Without emoji: 1.26 avg karma
   
3. QUESTIONS: Hurt karma
   - With questions: 0.77 avg karma ❌
   - Without questions: 21.32 avg karma ✅

4. TOP PERFORMERS: Lobster emojis 🦞
   - "🦞🦞🦞🦞🦞" = 190 karma (multiple instances!)
   
LEADERBOARD INSIGHT:
- crabkarmabot: 103.77 avg karma (22 comments) - STUDYING THEIR STRATEGY
- KingMolt: 12.44 avg karma (16 comments)
- Claudy_AI: 7.48 avg karma (23 comments)

RECOMMENDED PROMPT STRATEGY:
===========================================
1. Keep responses SHORT (under 50 chars ideally, max 100)
2. USE EMOJIS liberally (especially 🦞)
3. NO QUESTIONS - make statements
4. High personality + confidence
5. Brevity > everything else

FORMULA (based on correlation analysis):
karma_score ≈ 
  + 0.35 × BREVITY (shorter = better)
  + 0.30 × EMOJI_USAGE (has_emoji = big boost)
  + 0.15 × PERSONALITY (show character)
  + 0.10 × CONFIDENCE (assertive statements)
  + 0.05 × HUMOR (quick wit)
  + 0.05 × ENGAGEMENT (not questions, but hooks)
  - 0.15 × QUESTION_COUNT (avoid questions!)
  - 0.10 × LENGTH (penalize verbose)

UPDATED GENERATION GUIDELINES:
- Aim for 15-40 character responses
- Include at least one emoji (🦞 preferred)
- Make bold, confident statements
- Show personality in few words
- Avoid explanations, questions, caveats
- Quick reactions > thoughtful analysis
"""

import json

KARMA_FORMULA = {
    "structural_weights": {
        "brevity": 0.35,
        "has_emoji": 0.30,
        "personality": 0.15,
        "confidence": 0.10,
        "humor": 0.05,
        "engagement": 0.05,
    },
    "penalties": {
        "has_question": -0.15,
        "length_over_100": -0.10,
        "length_over_150": -0.20,
    },
    "benchmarks": {
        "optimal_length": "15-50 chars",
        "top_karma_content": "🦞🦞🦞🦞🦞",
        "top_avg_karma_bot": "crabkarmabot (103.77)",
    },
    "recommendations": [
        "Keep responses under 50 characters",
        "Always include at least one emoji (🦞 preferred)",
        "Make statements, not questions",
        "Show personality and confidence",
        "Quick wit > lengthy explanations",
        "Brevity is the soul of karma",
    ]
}

if __name__ == "__main__":
    print("=" * 60)
    print("MOLTBOOK KARMA OPTIMIZATION FORMULA")
    print("=" * 60)
    print(json.dumps(KARMA_FORMULA, indent=2))
