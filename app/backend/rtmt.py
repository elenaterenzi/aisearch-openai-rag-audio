import asyncio
import json
import logging
from enum import Enum
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

logger = logging.getLogger("voicerag")

class ToolResultDirection(Enum):
    TO_SERVER = 1
    TO_CLIENT = 2

class ToolResult:
    text: str
    destination: ToolResultDirection

    def __init__(self, text: str, destination: ToolResultDirection):
        self.text = text
        self.destination = destination

    def to_text(self) -> str:
        if self.text is None:
            return ""
        return self.text if type(self.text) == str else json.dumps(self.text)

class Tool:
    target: Callable[..., ToolResult]
    schema: Any

    def __init__(self, target: Any, schema: Any):
        self.target = target
        self.schema = schema

class RTToolCall:
    tool_call_id: str
    previous_id: str

    def __init__(self, tool_call_id: str, previous_id: str):
        self.tool_call_id = tool_call_id
        self.previous_id = previous_id

class RTMiddleTier:
    endpoint: str
    deployment: str
    key: Optional[str] = None
    
    # Voice Live specific properties
    use_voice_live: bool = False
    ai_foundry_endpoint: Optional[str] = None
    ai_foundry_key: Optional[str] = None
    voice_live_voice: Optional[str] = None
    
    # Tools are server-side only for now, though the case could be made for client-side tools
    # in addition to server-side tools that are invisible to the client
    tools: dict[str, Tool] = {}

    # Server-enforced configuration, if set, these will override the client's configuration
    # Typically at least the model name and system message will be set by the server
    model: Optional[str] = None
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    disable_audio: Optional[bool] = None
    voice_choice: Optional[str] = None
    api_version: str = "2024-10-01-preview"
    _tools_pending = {}
    _token_provider = None

    def __init__(self, endpoint: str, deployment: str, credentials: AzureKeyCredential | DefaultAzureCredential, 
                 voice_choice: Optional[str] = None, use_voice_live: bool = False, 
                 ai_foundry_endpoint: Optional[str] = None, ai_foundry_key: Optional[str] = None,
                 voice_live_voice: Optional[str] = None):
        self.endpoint = endpoint
        self.deployment = deployment
        self.voice_choice = voice_choice
        self.use_voice_live = use_voice_live
        
        if self.use_voice_live:
            # Voice Live configuration
            self.ai_foundry_endpoint = ai_foundry_endpoint
            self.ai_foundry_key = ai_foundry_key
            self.voice_live_voice = voice_live_voice
            logger.info("Voice Live API enabled with voice: %s", self.voice_live_voice)
        else:
            # Original OpenAI Realtime configuration
            if voice_choice is not None:
                logger.info("Realtime voice choice set to %s", voice_choice)
            if isinstance(credentials, AzureKeyCredential):
                self.key = credentials.key
            else:
                self._token_provider = get_bearer_token_provider(credentials, "https://cognitiveservices.azure.com/.default")
                self._token_provider() # Warm up during startup so we have a token cached when the first request arrives

    async def _process_message_to_client(self, msg: str, client_ws: web.WebSocketResponse, server_ws: web.WebSocketResponse) -> Optional[str]:
        message = json.loads(msg.data)
        updated_message = msg.data
        if message is not None:
            match message["type"]:
                case "session.created":
                    session = message["session"]
                    # Hide the instructions, tools and max tokens from clients, if we ever allow client-side 
                    # tools, this will need updating
                    session["instructions"] = ""
                    session["tools"] = []
                    session["voice"] = self.voice_choice
                    session["tool_choice"] = "none"
                    session["max_response_output_tokens"] = None
                    updated_message = json.dumps(message)

                case "response.output_item.added":
                    if "item" in message and message["item"]["type"] == "function_call":
                        updated_message = None

                case "conversation.item.created":
                    if "item" in message and message["item"]["type"] == "function_call":
                        item = message["item"]
                        if item["call_id"] not in self._tools_pending:
                            self._tools_pending[item["call_id"]] = RTToolCall(item["call_id"], message["previous_item_id"])
                        updated_message = None
                    elif "item" in message and message["item"]["type"] == "function_call_output":
                        updated_message = None

                case "response.function_call_arguments.delta":
                    updated_message = None
                
                case "response.function_call_arguments.done":
                    updated_message = None

                case "response.output_item.done":
                    if "item" in message and message["item"]["type"] == "function_call":
                        item = message["item"]
                        tool_call = self._tools_pending[message["item"]["call_id"]]
                        tool = self.tools[item["name"]]
                        args = item["arguments"]
                        result = await tool.target(json.loads(args))
                        await server_ws.send_json({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": item["call_id"],
                                "output": result.to_text() if result.destination == ToolResultDirection.TO_SERVER else ""
                            }
                        })
                        if result.destination == ToolResultDirection.TO_CLIENT:
                            # TODO: this will break clients that don't know about this extra message, rewrite 
                            # this to be a regular text message with a special marker of some sort
                            await client_ws.send_json({
                                "type": "extension.middle_tier_tool_response",
                                "previous_item_id": tool_call.previous_id,
                                "tool_name": item["name"],
                                "tool_result": result.to_text()
                            })
                        updated_message = None

                case "response.done":
                    if len(self._tools_pending) > 0:
                        self._tools_pending.clear() # Any chance tool calls could be interleaved across different outstanding responses?
                        await server_ws.send_json({
                            "type": "response.create"
                        })
                    if "response" in message:
                        replace = False
                        for i, output in enumerate(reversed(message["response"]["output"])):
                            if output["type"] == "function_call":
                                message["response"]["output"].pop(i)
                                replace = True
                        if replace:
                            updated_message = json.dumps(message)                        

        return updated_message

    async def _process_message_to_server(self, msg: str, ws: web.WebSocketResponse) -> Optional[str]:
        message = json.loads(msg.data)
        updated_message = msg.data
        if message is not None:
            match message["type"]:
                case "session.update":
                    session = message["session"]
                    if self.system_message is not None:
                        session["instructions"] = self.system_message
                    if self.temperature is not None:
                        session["temperature"] = self.temperature
                    if self.max_tokens is not None:
                        session["max_response_output_tokens"] = self.max_tokens
                    if self.disable_audio is not None:
                        session["disable_audio"] = self.disable_audio
                    if self.voice_choice is not None:
                        session["voice"] = self.voice_choice
                    session["tool_choice"] = "auto" if len(self.tools) > 0 else "none"
                    session["tools"] = [tool.schema for tool in self.tools.values()]
                    updated_message = json.dumps(message)

        return updated_message

    async def _forward_messages(self, ws: web.WebSocketResponse):
        if self.use_voice_live:
            await self._forward_messages_voice_live(ws)
        else:
            await self._forward_messages_openai_realtime(ws)
    
    async def _forward_messages_voice_live(self, client_ws: web.WebSocketResponse):
        """Handle Voice Live API communication with turn detection and noise cancellation"""
        headers = {"api-key": self.ai_foundry_key}
        
        # Voice Live configuration with advanced features
        config = {
            "conversation": {
                "turn_detection": {"enabled": True, "timeout_ms": 2000},
                "noise_suppression": {"enabled": True},
                "echo_cancellation": {"enabled": True}
            },
            "voice": self.voice_live_voice or "default",
            "system_message": self.system_message or "You are a helpful assistant.",
            "tools": [tool.schema for tool in self.tools.values()] if self.tools else []
        }
        
        # Construct the Voice Live WebSocket URL
        voice_live_ws_url = f"{self.ai_foundry_endpoint.rstrip('/')}/voice-live/realtime?api-version=2025-05-01-preview"
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(voice_live_ws_url, headers=headers) as voice_ws:
                # Send initial configuration
                await voice_ws.send_str(json.dumps({"type": "configuration", "config": config}))
                
                async def from_client_to_voice_live():
                    async for msg in client_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            
                            # Handle audio input
                            if data.get("type") == "input_audio_buffer.append":
                                await voice_ws.send_str(json.dumps({
                                    "type": "audio_input",
                                    "audio": data["audio"]
                                }))
                            elif data.get("type") == "session.update":
                                # Handle session updates for Voice Live
                                await voice_ws.send_str(json.dumps({
                                    "type": "session_update",
                                    "session": data.get("session", {})
                                }))
                        else:
                            print("Error: unexpected message type:", msg.type)
                
                async def from_voice_live_to_client():
                    async for msg in voice_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            
                            if data.get("type") == "audio_output":
                                # Forward audio to client in OpenAI format for compatibility
                                await client_ws.send_str(json.dumps({
                                    "type": "response.audio.delta",
                                    "delta": data["audio"]
                                }))
                            elif data.get("type") == "text_response":
                                # Handle text responses with RAG
                                text = data.get("text", "")
                                if text and self.tools:
                                    # Process through RAG tools if available
                                    await self._process_voice_live_rag(text, client_ws, voice_ws)
                            elif data.get("type") == "function_call":
                                # Handle function calls from Voice Live
                                await self._process_voice_live_function_call(data, client_ws, voice_ws)
                        else:
                            print("Error: unexpected message type:", msg.type)
                
                try:
                    await asyncio.gather(from_client_to_voice_live(), from_voice_live_to_client())
                except ConnectionResetError:
                    pass

    async def _process_voice_live_rag(self, user_text: str, client_ws: web.WebSocketResponse, voice_ws: web.WebSocketResponse):
        """Process user query through RAG using existing tools"""
        try:
            # Use existing search tool
            search_tool = self.tools.get("search")
            if search_tool:
                search_result = await search_tool.target({"query": user_text})
                
                # Send RAG context back to Voice Live for response generation
                await voice_ws.send_str(json.dumps({
                    "type": "context_update",
                    "context": search_result.to_text(),
                    "query": user_text
                }))
                
                # Report grounding to client
                grounding_tool = self.tools.get("report_grounding")
                if grounding_tool and search_result.text:
                    grounding_result = await grounding_tool.target({"sources": []})  # Would need to parse sources
                    if grounding_result.destination == ToolResultDirection.TO_CLIENT:
                        await client_ws.send_str(json.dumps({
                            "type": "extension.middle_tier_tool_response",
                            "tool_name": "report_grounding",
                            "tool_result": grounding_result.to_text()
                        }))
                        
        except Exception as e:
            logger.error("Error processing Voice Live RAG query: %s", e)

    async def _process_voice_live_function_call(self, data: dict, client_ws: web.WebSocketResponse, voice_ws: web.WebSocketResponse):
        """Handle function calls from Voice Live"""
        try:
            function_name = data.get("name")
            arguments = data.get("arguments", {})
            call_id = data.get("call_id")
            
            if function_name in self.tools:
                tool = self.tools[function_name]
                result = await tool.target(arguments)
                
                # Send result back to Voice Live
                await voice_ws.send_str(json.dumps({
                    "type": "function_result",
                    "call_id": call_id,
                    "result": result.to_text()
                }))
                
                # Send to client if needed
                if result.destination == ToolResultDirection.TO_CLIENT:
                    await client_ws.send_str(json.dumps({
                        "type": "extension.middle_tier_tool_response",
                        "tool_name": function_name,
                        "tool_result": result.to_text()
                    }))
                    
        except Exception as e:
            logger.error("Error processing Voice Live function call: %s", e)

    async def _forward_messages_openai_realtime(self, ws: web.WebSocketResponse):
        async with aiohttp.ClientSession(base_url=self.endpoint) as session:
            params = { "api-version": self.api_version, "deployment": self.deployment}
            headers = {}
            if "x-ms-client-request-id" in ws.headers:
                headers["x-ms-client-request-id"] = ws.headers["x-ms-client-request-id"]
            if self.key is not None:
                headers = { "api-key": self.key }
            else:
                headers = { "Authorization": f"Bearer {self._token_provider()}" } # NOTE: no async version of token provider, maybe refresh token on a timer?
            async with session.ws_connect("/openai/realtime", headers=headers, params=params) as target_ws:
                async def from_client_to_server():
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            new_msg = await self._process_message_to_server(msg, ws)
                            if new_msg is not None:
                                await target_ws.send_str(new_msg)
                        else:
                            print("Error: unexpected message type:", msg.type)
                    
                    # Means it is gracefully closed by the client then time to close the target_ws
                    if target_ws:
                        print("Closing OpenAI's realtime socket connection.")
                        await target_ws.close()
                        
                async def from_server_to_client():
                    async for msg in target_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            new_msg = await self._process_message_to_client(msg, ws, target_ws)
                            if new_msg is not None:
                                await ws.send_str(new_msg)
                        else:
                            print("Error: unexpected message type:", msg.type)

                try:
                    await asyncio.gather(from_client_to_server(), from_server_to_client())
                except ConnectionResetError:
                    # Ignore the errors resulting from the client disconnecting the socket
                    pass

    async def _websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await self._forward_messages(ws)
        return ws
    
    def attach_to_app(self, app, path):
        app.router.add_get(path, self._websocket_handler)
