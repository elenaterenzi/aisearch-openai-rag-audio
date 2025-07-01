# Voice Live Deployment Guide

This guide explains how to deploy the Voice Live API integration with your existing RAG application using Azure AI Foundry.

## What's Included

### Infrastructure Components Added:
1. **Azure AI Foundry Resource** - Multi-service resource that provides Voice Live API endpoints
2. **Role Assignments** - Cognitive Services User role for the container app managed identity
3. **Environment Variables** - Voice Live configuration in the container app

### Code Changes:
1. **Backend RTMiddleTier** - Updated to support Voice Live WebSocket connections
2. **Session Configuration** - Voice Live specific settings (VAD, audio formats, transcription)
3. **Authentication** - Support for AI Foundry credentials and managed identity

## Deployment Steps

### 1. Set Environment Variables

Add these to your `.env` file or Azure environment:

```bash
# Enable Voice Live
USE_VOICE_LIVE=true

# AI Foundry Configuration
AZURE_AI_FOUNDRY_LOCATION=swedencentral
AZURE_AI_FOUNDRY_SERVICE=your-ai-foundry-name
AZURE_AI_FOUNDRY_RESOURCE_GROUP=your-rg
```

### 2. Deploy Infrastructure

```bash
# Initialize and deploy with azd
azd up

# Or deploy manually with Azure CLI
az deployment sub create \
  --location swedencentral \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json
```

### 3. Verify Deployment

Check that these resources were created:
- Azure Speech Services instance
- Azure AI Hub (if not reusing existing)
- Role assignments for container app managed identity

## Key Benefits

### Voice Live Features Enabled:
- **Better VAD**: Server-side voice activity detection with noise suppression
- **Improved Audio Quality**: Enhanced audio processing pipeline
- **Lower Latency**: Optimized for real-time conversations
- **Background Noise Handling**: Built-in noise suppression and echo cancellation

### RAG Integration Preserved:
- **Search Tools**: All existing search functionality continues working
- **Function Calling**: Tool definitions and execution remain unchanged
- **Embedding Pipeline**: Azure AI Search vector operations unaffected
- **Grounding**: Citation and source attribution intact

## Configuration Options

### Voice Live Session Settings:
```json
{
  "turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 500
  },
  "input_audio_format": "pcm16",
  "output_audio_format": "pcm16",
  "input_audio_transcription": {
    "model": "whisper-1"
  }
}
```

### Model Selection:
- **gpt-4o**: Default model for Voice Live
- **gpt-4o-mini**: Available for faster, lower-cost operations

## Troubleshooting

### Common Issues:
1. **Authentication Errors**: Ensure managed identity has Cognitive Services User role
2. **Endpoint Errors**: Verify Speech Services region supports Voice Live
3. **Model Availability**: Check that gpt-4o is available in your region

### Testing:
```bash
# Test with Voice Live enabled
export USE_VOICE_LIVE=true
cd app && python -m backend.app

# Test fallback to OpenAI Realtime
export USE_VOICE_LIVE=false
cd app && python -m backend.app
```

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_VOICE_LIVE` | Enable Voice Live API | `false` |
| `AZURE_SPEECH_ENDPOINT` | Speech Services endpoint | Auto-generated |
| `AZURE_SPEECH_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `AZURE_AI_HUB_NAME` | AI Hub resource name | Auto-generated |

## Migration Path

The deployment supports both APIs simultaneously:
1. **Phase 1**: Deploy Voice Live infrastructure alongside existing OpenAI Realtime
2. **Phase 2**: Test Voice Live with `USE_VOICE_LIVE=true`
3. **Phase 3**: Switch production traffic to Voice Live
4. **Phase 4**: Optionally remove OpenAI Realtime resources

This ensures zero-downtime migration and easy rollback capability.
