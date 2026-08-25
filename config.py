"""
Root level configuration for the jobspy project.
Contains AI agent configuration and other settings.
"""

# AI Configuration
# Set AI_PROVIDER to one of: "nvidia", "anthropic", "openai", "local"
# or leave as None to fall back to rule-based string matching.
# API keys should be set in .env file (see .env.example)

AI_PROVIDER = "nvidia"  # <-- Use NVIDIA as requested
AI_MODEL = "https://integrate.api.nvidia.com/v1"  # Example NVIDIA model
# API key: set NVIDIA_API_KEY in .env file
AI_API_KEY = None  # Will be loaded from .env if present

# Example for Anthropic (Claude):
# AI_PROVIDER = "anthropic"
# AI_MODEL = "claude-3-opus-20240229"
# API key: set ANTHROPIC_API_KEY in .env

# Example for OpenAI:
# AI_PROVIDER = "openai"
# AI_MODEL = "gpt-4-turbo"
# API key: set OPENAI_API_KEY in .env

# Scraper settings can be added here if desired in the future