import asyncio
import json
import logging
from enum import Enum
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider, EnvironmentCredential

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
    is_voice_live: bool = False
    voice_live_region: Optional[str] = None
    
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

    def __init__(self, endpoint: str, deployment: str, credentials: AzureKeyCredential | DefaultAzureCredential, voice_choice: Optional[str] = None, use_voice_live: bool = False):
        self.endpoint = endpoint
        self.deployment = deployment
        self.voice_choice = voice_choice
        self.is_voice_live = use_voice_live
        
        # Extract region from endpoint for Voice Live
        # According to the official docs, extracting the region from the endpoint is not required for Voice Live.
        # The region is not needed for authentication or connection.
        # See: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-quickstart
            
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

                # Add this new case for user audio transcription
                case "conversation.item.input_audio_transcription.completed":
                    if "transcript" in message:
                        logger.info("!!!TX!!! User audio transcribed: %s", message["transcript"])
                    # Let this message pass through to the client
                    updated_message = msg.data

                # Add this new case for AI response transcription
                case "response.audio_transcript.delta":
                    #if "delta" in message:
                    #    logger.info("!!!TX!!! AI response transcript delta: %s", message["delta"])
                    # Let this message pass through to the client
                    updated_message = msg.data

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
                    
                    # Configure Voice Live specific settings
                    if self.is_voice_live:
                        # OLD
                        # Voice Live session configuration based on actual API
                        # session["turn_detection"] = {
                        #     "type": "server_vad",
                        #     "threshold": 0.5,
                        #     "prefix_padding_ms": 300,
                        #     "silence_duration_ms": 500
                        # }
                        #NEW
                        use_semantic_vad = not(self.deployment.startswith("gpt-4o") or self.deployment.endswith("--realtime-preview"))
                        if use_semantic_vad:
                            session["turn_detection"] = {
                                "type": "azure_semantic_vad",
                                "threshold": 0.3,
                                "prefix_padding_ms": 200,
                                "silence_duration_ms": 200,
                                "remove_filler_words": False,
                                "end_of_utterance_detection": {
                                    "model": "semantic_detection_v1",
                                    "threshold": 0.01,
                                    "timeout": 2,
                                },
                            }
                        else:
                            session["turn_detection"] = {
                                "type": "server_vad",
                                "threshold": 0.3,
                                "prefix_padding_ms": 200,
                                "silence_duration_ms": 200,
                                "remove_filler_words": False,
                            }
                        # Audio noise reduction
                        session["input_audio_noise_reduction"] = {
                            "type": "azure_deep_noise_suppression"
                        }
                        # Echo cancellation
                        session["input_audio_echo_cancellation"] = {
                            "type": "server_echo_cancellation"
                        }
                        # END NEW
                        # OLD but kept
                        # Voice Live specific configuration
                        session["input_audio_format"] = "pcm16"
                        session["output_audio_format"] = "pcm16"
                        session["input_audio_transcription"] = {
                            "model": "whisper-1"
                        }
                        # end of OLD
                    
                    session["tool_choice"] = "auto" if len(self.tools) > 0 else "none"
                    session["tools"] = [tool.schema for tool in self.tools.values()]
                    updated_message = json.dumps(message)

        return updated_message

    async def _forward_messages(self, ws: web.WebSocketResponse):
        if self.is_voice_live:
            # Voice Live requires direct WebSocket connection with full URL
            # Convert https:// to wss:// for WebSocket
            ws_endpoint = self.endpoint.replace("https://", "wss://").rstrip("/")
            params = { 
                "api-version": "2025-05-01-preview",
                "model": self.deployment or "gpt-4o"
            }
            ws_path = "/voice-live/realtime"
            
            # # Build complete WebSocket URL for Voice Live
            # param_string = "&".join([f"{k}={v}" for k, v in params.items()])
            # full_ws_url = f"{ws_endpoint}{ws_path}?{param_string}"
            logger.info("Connecting to Voice Live WebSocket at %s", ws_endpoint + ws_path)
            
            headers = {}
            # Always set x-ms-client-request-id in headers, generate one if not present
            if "x-ms-client-request-id" in ws.headers:
                headers["x-ms-client-request-id"] = ws.headers["x-ms-client-request-id"]
            else:
                import uuid
                headers["x-ms-client-request-id"] = str(uuid.uuid4())
            if self.key is not None:
                headers["api-key"] = self.key
                logger.info("Using API key for Voice Live WebSocket connection")
            else:
                logger.info("Using Bearer token for Voice Live WebSocket connection")
                headers["Authorization"] = f"Bearer {self._token_provider()}"
            
            # logger.info("Headers for Voice Live WebSocket connection: %s", headers)
            # Direct WebSocket connection for Voice Live
            import aiohttp
            async with aiohttp.ClientSession(base_url=ws_endpoint) as session:
                async with session.ws_connect(ws_path, headers=headers, params=params) as target_ws:
                    await self._handle_websocket_communication(ws, target_ws)
            
        else:
            # Original OpenAI Realtime API (uses base_url + relative path)
            async with aiohttp.ClientSession(base_url=self.endpoint) as session:
                params = { "api-version": self.api_version, "deployment": self.deployment}
                ws_path = "/openai/realtime"
                    
                headers = {}
                if "x-ms-client-request-id" in ws.headers:
                    headers["x-ms-client-request-id"] = ws.headers["x-ms-client-request-id"]
                if self.key is not None:
                    headers = { "api-key": self.key }
                else:
                    headers = { "Authorization": f"Bearer {self._token_provider()}" }
                async with session.ws_connect(ws_path, headers=headers, params=params) as target_ws:
                    await self._handle_websocket_communication(ws, target_ws)

    async def _handle_websocket_communication(self, ws: web.WebSocketResponse, target_ws):
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
                print("Closing realtime socket connection.")
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
