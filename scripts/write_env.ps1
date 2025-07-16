# Define the .env file path
$envFilePath = "app\backend\.env"

# Clear the contents of the .env file
Set-Content -Path $envFilePath -Value ""

# Append new values to the .env file
$azureOpenAiEndpoint = azd env get-value AZURE_OPENAI_ENDPOINT
$azureOpenAiRealtimeDeployment = azd env get-value AZURE_OPENAI_REALTIME_DEPLOYMENT
$azureOpenAiRealtimeVoiceChoice = azd env get-value AZURE_OPENAI_REALTIME_VOICE_CHOICE
$azureSearchEndpoint = azd env get-value AZURE_SEARCH_ENDPOINT
$azureSearchIndex = azd env get-value AZURE_SEARCH_INDEX
$azureTenantId = azd env get-value AZURE_TENANT_ID
$azureSearchSemanticConfiguration = azd env get-value AZURE_SEARCH_SEMANTIC_CONFIGURATION
$azureSearchIdentifierField = azd env get-value AZURE_SEARCH_IDENTIFIER_FIELD
$azureSearchTitleField = azd env get-value AZURE_SEARCH_TITLE_FIELD
$azureSearchContentField = azd env get-value AZURE_SEARCH_CONTENT_FIELD
$azureSearchEmbeddingField = azd env get-value AZURE_SEARCH_EMBEDDING_FIELD
$azureSearchUseVectorQuery = azd env get-value AZURE_SEARCH_USE_VECTOR_QUERY

# Voice Live API environment variables
$useVoiceLive = azd env get-value USE_VOICE_LIVE
$azureAiFoundryEndpoint = azd env get-value AZURE_AI_FOUNDRY_ENDPOINT
$azureAiFoundryApiKey = azd env get-value AZURE_AI_FOUNDRY_API_KEY
$voiceLiveVoice = azd env get-value VOICE_LIVE_VOICE

Add-Content -Path $envFilePath -Value "AZURE_OPENAI_ENDPOINT=$azureOpenAiEndpoint"
Add-Content -Path $envFilePath -Value "AZURE_OPENAI_REALTIME_DEPLOYMENT=$azureOpenAiRealtimeDeployment"
Add-Content -Path $envFilePath -Value "AZURE_OPENAI_REALTIME_VOICE_CHOICE=$azureOpenAiRealtimeVoiceChoice"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_ENDPOINT=$azureSearchEndpoint"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_INDEX=$azureSearchIndex"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_SEMANTIC_CONFIGURATION=$azureSearchSemanticConfiguration"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_IDENTIFIER_FIELD=$azureSearchIdentifierField"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_TITLE_FIELD=$azureSearchTitleField"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_CONTENT_FIELD=$azureSearchContentField"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_EMBEDDING_FIELD=$azureSearchEmbeddingField"
Add-Content -Path $envFilePath -Value "AZURE_SEARCH_USE_VECTOR_QUERY=$azureSearchUseVectorQuery"
Add-Content -Path $envFilePath -Value "AZURE_TENANT_ID=$azureTenantId"

# Add Voice Live configuration when enabled
if ($useVoiceLive -eq "true") {
    Add-Content -Path $envFilePath -Value "USE_VOICE_LIVE=$useVoiceLive"
    Add-Content -Path $envFilePath -Value "AZURE_AI_FOUNDRY_ENDPOINT=$azureAiFoundryEndpoint"
    Add-Content -Path $envFilePath -Value "AZURE_AI_FOUNDRY_API_KEY=$azureAiFoundryApiKey"
    Add-Content -Path $envFilePath -Value "VOICE_LIVE_VOICE=$voiceLiveVoice"
} else {
    # Add USE_VOICE_LIVE=false for clarity even when not using Voice Live
    Add-Content -Path $envFilePath -Value "USE_VOICE_LIVE=false"
}
