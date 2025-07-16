@description('Name of the AI Foundry service')
param aiFoundryServiceName string

@description('Location for the AI Foundry service')
param location string

@description('Tags to apply to the AI Foundry service')
param tags object = {}

@description('Principal ID for role assignments')
param principalId string

@description('Principal type for role assignments')
param principalType string

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: aiFoundryServiceName
  location: location
  tags: tags
  kind: 'AIServices'
  properties: {
    customSubDomainName: aiFoundryServiceName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
  sku: {
    name: 'S0'
  }
}

// Role assignment for the user/service principal
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiFoundry
  name: guid(aiFoundry.id, principalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: principalId
    principalType: principalType
  }
}

@description('AI Foundry service name')
output name string = aiFoundry.name

@description('AI Foundry service endpoint (AI Foundry format)')
output endpoint string = replace(aiFoundry.properties.endpoint, '.cognitiveservices.azure.com', '.services.ai.azure.com')

@description('AI Foundry service API key')
output apiKey string = aiFoundry.listKeys().key1

@description('AI Foundry service resource ID')
output resourceId string = aiFoundry.id
