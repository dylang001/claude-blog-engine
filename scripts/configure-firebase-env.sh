#!/bin/bash
# Configure Firebase Functions environment variables
# Run this script to set all required env vars in Firebase

set -e

echo "Configuring Firebase Functions environment variables..."
echo ""
echo "Reading values from .env file..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file with your environment variables."
    exit 1
fi

# Function to safely get env var
get_env() {
    grep "^$1=" .env | cut -d'=' -f2- | sed 's/^"//;s/"$//'
}

# Read values
WP_BASE_URL=$(get_env WP_BASE_URL)
WP_USERNAME=$(get_env WP_USERNAME)
WP_APP_PASSWORD=$(get_env WP_APP_PASSWORD)
DATAFORSEO_LOGIN=$(get_env DATAFORSEO_LOGIN)
DATAFORSEO_PASSWORD=$(get_env DATAFORSEO_PASSWORD)
ANTHROPIC_API_KEY=$(get_env ANTHROPIC_API_KEY)

echo "Setting Firebase Functions config..."
echo ""

# Set WordPress config
if [ -n "$WP_APP_PASSWORD" ]; then
    echo "Setting WP_APP_PASSWORD..."
    firebase functions:config:set wp.app_password="$WP_APP_PASSWORD"
fi

if [ -n "$WP_BASE_URL" ]; then
    echo "Setting WP_BASE_URL..."
    firebase functions:config:set wp.base_url="$WP_BASE_URL"
fi

if [ -n "$WP_USERNAME" ]; then
    echo "Setting WP_USERNAME..."
    firebase functions:config:set wp.username="$WP_USERNAME"
fi

# Set DataForSEO config
if [ -n "$DATAFORSEO_LOGIN" ]; then
    echo "Setting DATAFORSEO_LOGIN..."
    firebase functions:config:set dataforseo.login="$DATAFORSEO_LOGIN"
fi

if [ -n "$DATAFORSEO_PASSWORD" ]; then
    echo "Setting DATAFORSEO_PASSWORD..."
    firebase functions:config:set dataforseo.password="$DATAFORSEO_PASSWORD"
fi

# Set Anthropic config
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Setting ANTHROPIC_API_KEY..."
    firebase functions:config:set anthropic.api_key="$ANTHROPIC_API_KEY"
fi

echo ""
echo "✅ Environment variables configured!"
echo ""
echo "Redeploying functions to apply changes..."
firebase deploy --only functions

echo ""
echo "🎉 Done! Your functions now have access to the environment variables."
