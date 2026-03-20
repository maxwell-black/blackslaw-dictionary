#!/bin/bash
cd /Users/maxwellblack/blackslaw-dictionary

# Initialize git
git init
git add .
git commit -m "Initial commit - Blacks Law Dictionary site"

# Check if gh is installed
if command -v gh &> /dev/null; then
    echo "GitHub CLI found, creating repo..."
    gh repo create blackslaw-dictionary --public --description "Free searchable Black's Law Dictionary (1910)" --source=. --remote=origin --push
else
    echo "GitHub CLI not found. Please install it:"
    echo "brew install gh"
    echo "Then run: gh auth login"
fi
