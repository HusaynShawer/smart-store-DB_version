"""
Model configuration module for Smart Store Assistant.
"""

# Vision Model - Gemini/Gemma
VISION_MODEL = "gemma-3-27b-it"
VISION_PROVIDER = "gemini"

# Voice Model - OpenAI Whisper API
VOICE_MODEL = "whisper-1"
VOICE_PROVIDER = "openai"

# Text/Intent Models - Gemini
INTENT_MODEL = "gemma-3-27b-it"
INTENT_PROVIDER = "gemini"
AGENT_MODEL = "gemma-3-27b-it"
AGENT_PROVIDER = "gemini"
FAST_MODEL = "gemma-3-27b-it"
FAST_PROVIDER = "gemini"

# Inference Parameters
INTENT_TEMPERATURE = 0.1
AGENT_TEMPERATURE = 0.3
VISION_MAX_TOKENS = 50
INTENT_MAX_TOKENS = 200
AGENT_MAX_TOKENS = 1024

# Search Parameters
SEARCH_FUZZY_THRESHOLD = 0.70
SEARCH_MIN_RESULTS = 5
SEARCH_MAX_RESULTS = 10
