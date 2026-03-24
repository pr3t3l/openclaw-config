#!/bin/bash
# Sync keys from master .env to litellm.env
source ~/.openclaw/.env
cat > ~/.config/litellm/litellm.env << EOF
OPENAI_API_KEY=$OPENAI_API_KEY
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
GEMINI_API_KEY=$GEMINI_API_KEY
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
EOF
echo "Keys synced to litellm.env"
