# Google Drive Webhook Setup - Step by Step Guide

## Overview
Your webhook system is already coded and ready! You just need to connect it to Google Drive API. Here's exactly what happens:

1. **You register** a webhook with Google Drive saying "notify me at http://localhost:8000/webhooks/drive"
2. **Google Drive watches** your files for changes
3. **When files change**, Google sends a notification to your webhook endpoint
4. **Your app verifies** the notification using your webhook secret
5. **Your app processes** the changed file automatically

## Step 1: Google Cloud Console Setup

### 1.1 Create a Google Cloud Project
1. Go to https://console.cloud.google.com/
2. Sign in with your Google account
3. Click "Select a project" → "New Project"
4. Name it "RAG Chatbot" or similar
5. Click "Create"

### 1.2 Enable Google Drive API
1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on it and press "Enable"

### 1.3 Create OAuth Credentials
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth 2.0 Client IDs"
3. If prompted, configure OAuth consent screen:
   - Choose "External" user type
   - Fill in app name: "RAG Chatbot"
   - Add your email as developer contact
   - Save and continue through the steps
4. Back to creating OAuth client:
   - Application type: "Web application"
   - Name: "RAG Chatbot Client"
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
   - Click "Create"
5. **COPY** the Client ID and Client Secret - you'll need these!

## Step 2: Update Your .env File

Replace the placeholder values in your `.env` file:

```bash
GOOGLE_CLIENT_ID=your_actual_client_id_from_step_1.3
GOOGLE_CLIENT_SECRET=your_actual_client_secret_from_step_1.3
```

## Step 3: Understand the Webhook Registration Process

Here's what happens when you register a webhook:

### 3.1 Authentication Flow
```
User → Google OAuth → Your App Gets Access Token → Can Register Webhooks
```

### 3.2 Webhook Registration
```python
# This is what your app sends to Google Drive API:
{
    'id': 'unique-channel-id',
    'type': 'web_hook',
    'address': 'http://localhost:8000/webhooks/drive',  # Your endpoint
    'token': 'R2SGeD3ktlyNqW4Jbemgy_hVIr209mQK6owkMrz85EI'  # Your webhook secret
}
```

### 3.3 When Files Change
```
File Changed → Google Drive → Signs notification with your secret → 
Sends to http://localhost:8000/webhooks/drive → Your app verifies signature → 
Processes the file automatically
```

## Step 4: Testing the Setup

### 4.1 Test Authentication (Manual)
1. With your server running, visit: `http://localhost:8000/auth/google?client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET`
2. You'll be redirected to Google for authorization
3. After authorizing, you'll be redirected back to your app

### 4.2 Test Webhook Registration
Once authenticated, you can call your webhook setup endpoint:
```bash
curl -X POST "http://localhost:8000/webhooks/setup"
```

## Step 5: Real-World Usage

### For Testing (Simple Way)
1. Use your existing Google Drive URL processing: `http://localhost:8000/process-drive-url`
2. Paste a Google Drive document URL
3. Your app will process it without webhooks

### For Production (Automatic Way)
1. Complete the OAuth setup above
2. Register webhooks for specific folders or your entire drive
3. Any time you edit a Google Doc, your app will automatically:
   - Receive a webhook notification
   - Verify it's really from Google
   - Re-download and re-process the changed document
   - Update your Redis vector database

## Current Status ✅

Your system already has:
- ✅ Webhook endpoints (`/webhooks/drive`, `/webhooks/setup`)
- ✅ Signature verification using your webhook secret
- ✅ Automatic document processing pipeline
- ✅ Redis vector storage with change detection

You just need to:
- ⏳ Get Google OAuth credentials (Steps 1-2)
- ⏳ Test the authentication flow (Step 4)

## Security Note

Your webhook secret `R2SGeD3ktlyNqW4Jbemgy_hVIr209mQK6owkMrz85EI` ensures that only Google Drive can send valid notifications to your app. This prevents malicious actors from triggering false document processing. 