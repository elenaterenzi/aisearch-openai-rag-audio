#!/bin/bash

# Define the .env file path
ENV_FILE_PATH="app/backend/.env"

# Clear the contents of the .env file
> $ENV_FILE_PATH

# Append new values to the .env file
echo "AZURE_OPENAI_ENDPOINT=$(azd env get-value AZURE_OPENAI_ENDPOINT)" >> $ENV_FILE_PATH
echo "AZURE_OPENAI_REALTIME_DEPLOYMENT=$(azd env get-value AZURE_OPENAI_REALTIME_DEPLOYMENT)" >> $ENV_FILE_PATH
echo "AZURE_OPENAI_REALTIME_VOICE_CHOICE=$(azd env get-value AZURE_OPENAI_REALTIME_VOICE_CHOICE)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_ENDPOINT=$(azd env get-value AZURE_SEARCH_ENDPOINT)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_INDEX=$(azd env get-value AZURE_SEARCH_INDEX)" >> $ENV_FILE_PATH
echo "AZURE_TENANT_ID=$(azd env get-value AZURE_TENANT_ID)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_SEMANTIC_CONFIGURATION=$(azd env get-value AZURE_SEARCH_SEMANTIC_CONFIGURATION)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_IDENTIFIER_FIELD=$(azd env get-value AZURE_SEARCH_IDENTIFIER_FIELD)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_CONTENT_FIELD=$(azd env get-value AZURE_SEARCH_CONTENT_FIELD)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_TITLE_FIELD=$(azd env get-value AZURE_SEARCH_TITLE_FIELD)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_EMBEDDING_FIELD=$(azd env get-value AZURE_SEARCH_EMBEDDING_FIELD)" >> $ENV_FILE_PATH
echo "AZURE_SEARCH_USE_VECTOR_QUERY=$(azd env get-value AZURE_SEARCH_USE_VECTOR_QUERY)" >> $ENV_FILE_PATH

# Add Voice Live configuration conditionally
USE_VOICE_LIVE=$(azd env get-value USE_VOICE_LIVE)
if [ "$USE_VOICE_LIVE" = "true" ]; then
    echo "USE_VOICE_LIVE=$USE_VOICE_LIVE" >> $ENV_FILE_PATH
    echo "AZURE_AI_FOUNDRY_ENDPOINT=$(azd env get-value AZURE_AI_FOUNDRY_ENDPOINT)" >> $ENV_FILE_PATH
    echo "AZURE_AI_FOUNDRY_API_KEY=$(azd env get-value AZURE_AI_FOUNDRY_API_KEY)" >> $ENV_FILE_PATH
    echo "VOICE_LIVE_VOICE=$(azd env get-value VOICE_LIVE_VOICE)" >> $ENV_FILE_PATH
else
    # Add USE_VOICE_LIVE=false for clarity even when not using Voice Live
    echo "USE_VOICE_LIVE=false" >> $ENV_FILE_PATH
fi
