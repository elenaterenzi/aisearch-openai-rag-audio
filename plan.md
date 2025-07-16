# Implementation Plan: Voice Live API Integration with Feature Flag

## Overview
Add Azure Speech Service Voice Live API support to the existing VoiceRAG demo using a feature flag approach. This allows switching between Azure Speech Service Voice Live API and OpenAI Realtime API without creating new files, while preserving all existing RAG functionality.

## Requirements
- **Feature flag control**: Single environment variable (`USE_VOICE_LIVE`) to switch between APIs
- **Reuse existing files**: Modify `rtmt.py` and `app.py` instead of creating new files
- **Preserve RAG functionality**: Keep existing Azure AI Search integration unchanged
- **Demo-focused**: Simple implementation without testing complexity
- **Advanced Voice Features**: Enable turn detection, noise cancellation, and echo cancellation when using Voice Live

## Implementation Steps

### Step 1: Update Environment Configuration
**File to modify**: `app/backend/.env`

Add the feature flag and Voice Live configuration variables:
- `USE_VOICE_LIVE`: Boolean flag to choose between APIs (default: false)
- `AZURE_AI_FOUNDRY_ENDPOINT`: AI Foundry endpoint for Voice Live API
- `AZURE_AI_FOUNDRY_API_KEY`: AI Foundry API key for Voice Live
- `VOICE_LIVE_VOICE`: Voice model specific to Voice Live (e.g., available Voice Live voices)

Keep existing OpenAI Realtime and Azure Search configuration variables unchanged.

### Step 2: Modify RTMiddleTier for Voice Live Support
**File to modify**: `app/backend/rtmt.py`

Add Voice Live functionality to the existing RTMiddleTier class:

1. **Add Voice Live properties**: Add properties for AI Foundry endpoint, key, and voice selection
2. **Update constructor**: Accept Voice Live parameters and initialize accordingly
3. **Add Voice Live message forwarding method**: Handle WebSocket communication with Voice Live API
4. **Add RAG query processing method**: Process user queries through existing RAG tools with Voice Live
5. **Add function call processing method**: Handle Voice Live function calls for RAG tools
6. **Update main forwarding method**: Route to appropriate API based on feature flag
7. **Keep existing OpenAI Realtime methods**: Preserve all existing functionality for backward compatibility

### Step 3: Update Application Configuration
**File to modify**: `app/backend/app.py`

Update the app creation to support the feature flag:

1. **Check feature flag** at startup to determine which API to use
2. **Create RTMiddleTier** with appropriate configuration based on the flag
3. **Log API selection** for debugging purposes
4. **Preserve existing RAG tools attachment**: Ensure both APIs work with Azure AI Search

### Step 4: Update Dependencies
**File to modify**: `app/backend/requirements.txt`

No additional dependencies needed - Voice Live has integrated capabilities.

### Step 5: Optional Frontend Enhancement
**File to modify**: `app/frontend/src/hooks/useRealtime.tsx` (optional)

The existing frontend code will work with both APIs since we maintain the same WebSocket message format. Optionally add logging to indicate which API is active.

### Step 6: Update Infrastructure for Voice Live Support
**Files to modify**: `infra/main.bicep`, `infra/main.parameters.json`

Add infrastructure support for Voice Live API:

1. **Add Voice Live parameters**: Add parameters for AI Foundry endpoint and API key configuration
2. **Update container app environment variables**: Include Voice Live configuration in deployment
3. **Add conditional resource provisioning**: Optionally provision AI Foundry resources based on feature flag
4. **Update output variables**: Include Voice Live endpoints in infrastructure outputs

### Step 7: Update Deployment Scripts
**Files to modify**: `scripts/write_env.ps1`, `scripts/write_env.sh`

Update environment variable writing scripts to include Voice Live configuration:

1. **Add Voice Live environment variables**: Include AI Foundry endpoint and key variables
2. **Handle conditional configuration**: Only include Voice Live vars when feature flag is enabled
3. **Preserve existing OpenAI configuration**: Maintain backward compatibility

### Step 8: Update Azure Developer CLI Configuration
**File to modify**: `azure.yaml`

Update AZD configuration to support Voice Live deployment:

1. **Add Voice Live environment variables**: Include new configuration variables in AZD environment
2. **Update service parameters**: Ensure Voice Live configuration is passed to container apps
3. **Add deployment hooks**: Include any necessary post-deployment configuration for Voice Live

## Usage Instructions

### To use Voice Live API:
1. Set `USE_VOICE_LIVE=true` in your environment or AZD configuration
2. Configure AI Foundry endpoint: `AZURE_AI_FOUNDRY_ENDPOINT=your-ai-foundry-endpoint`
3. Set AI Foundry API key: `AZURE_AI_FOUNDRY_API_KEY=your-api-key`
4. Choose Voice Live voice: `VOICE_LIVE_VOICE=your-voice-name`
5. Deploy with `azd up` or update existing deployment with `azd deploy`

### To use OpenAI Realtime API (default):
1. Set `USE_VOICE_LIVE=false` (or leave unset)
2. Use existing OpenAI Realtime configuration
3. Deploy with `azd up` as normal

## Deployment Instructions

### Initial Deployment:
```bash
# Clone and navigate to repository
git clone <your-repo-url>
cd aisearch-openai-rag-audio

# Login to Azure
azd auth login

# Create new environment
azd env new

# For Voice Live deployment, set environment variables:
azd env set USE_VOICE_LIVE true
azd env set AZURE_AI_FOUNDRY_ENDPOINT "your-ai-foundry-endpoint"
azd env set AZURE_AI_FOUNDRY_API_KEY "your-api-key"
azd env set VOICE_LIVE_VOICE "your-voice-name"

# Deploy
azd up
```

### Switching Between APIs:
```bash
# Switch to Voice Live
azd env set USE_VOICE_LIVE true
azd env set AZURE_AI_FOUNDRY_ENDPOINT "your-ai-foundry-endpoint"
azd env set AZURE_AI_FOUNDRY_API_KEY "your-api-key"
azd deploy

# Switch back to OpenAI Realtime
azd env set USE_VOICE_LIVE false
azd deploy
```

## Voice Live API Advanced Features

When Voice Live mode is enabled, the following advanced features are automatically configured:

1. **Turn Detection**: Automatic detection of when user stops speaking (2-second timeout)
2. **Noise Suppression**: Built-in noise cancellation for cleaner audio input
3. **Echo Cancellation**: Prevents audio feedback loops
4. **High-Quality Voice Synthesis**: Azure Neural voices (configurable)

## Architecture Changes

### Voice Live Mode:
Audio flows through Voice Live API (via AI Foundry endpoint) for recognition and synthesis, with integrated RAG processing.

### OpenAI Realtime Mode:
Original flow remains unchanged - direct WebSocket communication with OpenAI Realtime API.

## Key Benefits

1. **Single Feature Flag**: Easy switching between APIs
2. **No New Files**: All changes fit within existing files
3. **Preserves RAG**: Existing Azure AI Search integration works with both APIs
4. **Demo-Ready**: Simple configuration without testing complexity
5. **Advanced Voice Features**: Turn detection and audio enhancement with Voice Live
6. **Backward Compatible**: Default behavior unchanged
7. **API Key Authentication**: Simple authentication suitable for demos

## Technical Notes

- Voice Live API uses WebSocket communication via AI Foundry endpoint
- Audio format compatibility: 16kHz PCM for Voice Live
- RAG tools work identically with both APIs
- System message and conversation context preserved across API modes
- Frontend requires no changes due to consistent WebSocket message format
- Voice Live has integrated RAG capabilities, no separate OpenAI text completion needed
- Infrastructure supports both APIs with feature flag-based deployment
- AZD environment variables control which API is deployed and configured

## Deployment Considerations

- **Environment Variables**: Voice Live configuration is passed through AZD environment variables to container apps
- **Resource Provisioning**: AI Foundry resources can be provisioned conditionally based on USE_VOICE_LIVE flag
- **Backward Compatibility**: Existing OpenAI Realtime deployments continue to work unchanged
- **Hot Switching**: Can switch between APIs by updating environment variables and redeploying
- **Cost Optimization**: Only provision resources for the API you're actually using

This implementation provides a clean, demo-focused way to explore Voice Live API capabilities while maintaining all existing VoiceRAG functionality and supporting production-ready deployment scenarios.