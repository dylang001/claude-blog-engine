#!/usr/bin/env python
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    print("=== Google Ads OAuth Refresh Token Generator ===")
    print("Make sure you created your credentials as a 'Desktop application' in Google Cloud Console.\n")
    
    client_id = input("Enter GOOGLE_ADS_CLIENT_ID: ").strip()
    client_secret = input("Enter GOOGLE_ADS_CLIENT_SECRET: ").strip()
    
    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.")
        sys.exit(1)
        
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    
    # Google Ads API Scope
    scopes = ["https://www.googleapis.com/auth/adwords"]
    
    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
        # Port 8080 or port 0 for random port
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            authorization_prompt_message="Please visit this URL to authorize the app: {url}",
            success_message="Authorization complete! You can close this window.",
            open_browser=True
        )
        
        print("\n=== SUCCESS ===")
        print("Copy the refresh token below and add it to your .env file:\n")
        print(f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}")
        print("===============")
        
    except Exception as e:
        print(f"\nError during authorization flow: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
