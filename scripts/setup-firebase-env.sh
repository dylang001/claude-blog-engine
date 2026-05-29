#!/bin/bash
# Setup Firebase Functions environment variables (modern approach)
# This script outputs the commands to run to set env vars in Firebase

echo "=========================================="
echo "Firebase Functions Environment Setup"
echo "=========================================="
echo ""
echo "The modern Firebase approach uses environment variables set in the console."
echo ""
echo "STEP 1: Go to Firebase Console"
echo "https://console.firebase.google.com/project/aeo-seo-agents-team/functions"
echo ""
echo "STEP 2: For each function, click 'Edit' and add these environment variables:"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Please create a .env file with your environment variables first."
    exit 1
fi

# Function to safely get env var
get_env() {
    grep "^$1=" .env | cut -d'=' -f2- | sed 's/^"//;s/"$//'
}

echo "Required Environment Variables:"
echo "--------------------------------"
echo ""
echo "WP_APP_PASSWORD=$(get_env WP_APP_PASSWORD)"
echo "WP_BASE_URL=$(get_env WP_BASE_URL)"
echo "WP_USERNAME=$(get_env WP_USERNAME)"
echo "DATAFORSEO_LOGIN=$(get_env DATAFORSEO_LOGIN)"
echo "DATAFORSEO_PASSWORD=$(get_env DATAFORSEO_PASSWORD)"
echo "ANTHROPIC_API_KEY=$(get_env ANTHROPIC_API_KEY | cut -c1-20)..."
echo ""

# Check for secrets
if command -v firebase &> /dev/null; then
    echo "STEP 3 (Optional): Set secrets using Firebase CLI"
    echo "------------------------------------------------"
    echo "For sensitive values, use Firebase Secrets:"
    echo ""
    echo "firebase functions:secrets:set WP_APP_PASSWORD"
    echo "firebase functions:secrets:set DATAFORSEO_PASSWORD"
    echo "firebase functions:secrets:set ANTHROPIC_API_KEY"
    echo ""
fi

echo "STEP 4: Redeploy functions"
echo "------------------------"
echo "firebase deploy --only functions"
echo ""
echo "✅ After setting env vars and redeploying, your functions will work!"
