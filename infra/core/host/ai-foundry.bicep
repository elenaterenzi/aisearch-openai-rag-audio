 @description('Name of the AI Foundry resource')
param name string

@description('Location for the AI Foundry resource')
param location string

@description('Tags to apply to the resource')
param tags object = {}

@description('SKU for the AI Foundry resource')
param sku string = 'S0'

@description('Whether to enable API key authentication')
param enableApiKeyAuth bool = true

@description('Principal ID for role assignment')
param principalId string = ''

@description('Principal type for role assignment')
@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('Whether to create role assignment')
param createRoleAssignment bool = true

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: sku
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    disableLocalAuth: !enableApiKeyAuth
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// Role assignment for user to access AI Foundry
resource aiFoundryUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignment && !empty(principalId)) {
  scope: aiFoundry
  name: guid(aiFoundry.id, principalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: principalId
    principalType: principalType
  }
}

@description('The resource ID of the AI Foundry account')
output resourceId string = aiFoundry.id

@description('The name of the AI Foundry account')
output name string = aiFoundry.name

@description('The endpoint of the AI Foundry account')
output endpoint string = aiFoundry.properties.endpoint

@description('The primary key of the AI Foundry account')
output primaryKey string = aiFoundry.listKeys().key1

@description('The secondary key of the AI Foundry account')
output secondaryKey string = aiFoundry.listKeys().key2

@description('The system assigned managed identity principal ID')
output systemAssignedMIPrincipalId string = aiFoundry.identity.principalId
