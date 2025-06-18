#!/usr/bin/env python3
"""
Script to set up Google Drive webhook for a specific folder
"""

import requests
import json
import sys
from config import settings

def setup_folder_webhook(folder_id: str):
    """Set up webhook for a specific Google Drive folder"""
    
    base_url = f"http://localhost:{settings.app_port}"
    
    print(f"Setting up webhook for folder: {folder_id}")
    print(f"Using server: {base_url}")
    
    # First, check if we're authenticated
    print("\n1. Checking authentication status...")
    try:
        response = requests.get(f"{base_url}/google-drive/folders")
        if response.status_code == 200:
            print("✅ Already authenticated with Google Drive")
        else:
            print("❌ Not authenticated. Please visit the following URL to authenticate:")
            print(f"   {base_url}/auth/google/login")
            print("\nAfter authentication, run this script again.")
            return False
    except Exception as e:
        print(f"❌ Error checking authentication: {e}")
        return False
    
    # Set up the webhook
    print(f"\n2. Setting up webhook for folder {folder_id}...")
    try:
        webhook_data = {"folder_id": folder_id}
        response = requests.post(
            f"{base_url}/webhooks/setup",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Webhook setup successful!")
            print(f"   Watch ID: {result.get('watch_id')}")
            print(f"   Webhook URL: {result.get('webhook_url')}")
            print(f"   Security: {'Enabled' if result.get('security_enabled') else 'Disabled'}")
            print(f"   Scope: {result.get('scope', 'unknown')}")
            
            if result.get('expiration'):
                print(f"   Expires: {result.get('expiration')}")
            
            return True
        else:
            error_data = response.json()
            print(f"❌ Webhook setup failed: {error_data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up webhook: {e}")
        return False

def main():
    """Main function"""
    folder_id = "1-QEzNq_RZI09jgkMnkyyNWo2fB533JBX"
    
    print("🚀 Google Drive Folder Webhook Setup")
    print("=" * 50)
    
    success = setup_folder_webhook(folder_id)
    
    if success:
        print("\n🎉 Webhook setup complete!")
        print("\nYour folder is now being monitored for changes.")
        print("When files are added, modified, or deleted in this folder,")
        print("they will be automatically processed and added to your knowledge base.")
    else:
        print("\n❌ Webhook setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 