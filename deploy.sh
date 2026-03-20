#!/bin/bash
# Black's Law Dictionary - GitHub Pages Deployment Script
# Run this after setting up GitHub authentication

set -e

echo "🚀 Deploying Black's Law Dictionary to GitHub Pages..."

# Check if authenticated
if ! gh auth status >/dev/null 2>&1; then
    echo "❌ Not authenticated to GitHub. Running 'gh auth login'..."
    gh auth login --git-protocol https
fi

cd ~/blackslaw-dictionary

# Check if repo exists on GitHub
REPO_EXISTS=$(gh repo view maxwelljblack/blackslaw-dictionary --json name 2>/dev/null | grep -c name || echo "0")

if [ "$REPO_EXISTS" = "0" ]; then
    echo "📦 Creating GitHub repository..."
    gh repo create blackslaw-dictionary --public --description "Free searchable Black's Law Dictionary (1910) - 12,000+ legal definitions" --source=. --remote=origin --push
else
    echo "📦 Repository exists, pushing changes..."
    git push -u origin main
fi

echo "🌐 Enabling GitHub Pages..."
gh api   --method PUT   -H "Accept: application/vnd.github+json"   /repos/maxwelljblack/blackslaw-dictionary/pages   -f source='{"branch":"main","path":"/"}' 2>/dev/null || echo "Pages may already be enabled"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Your site will be available at:"
echo "  - https://blackslaw.io (once DNS is configured)"
echo "  - https://maxwelljblack.github.io/blackslaw-dictionary (GitHub Pages URL)"
echo ""
echo "⏳ It may take 2-3 minutes for the site to be live."
