# Implementation Guide: Replacing GPT-4o Realtime with Voice Live API
Switching from the GPT-4o realtime model to the Azure Voice Live API involves a few straightforward changes. The overall architecture remains the same (client streaming audio to a backend, backend handling AI logic and streaming back audio), but you will point to a different WebSocket endpoint and update the session configuration to leverage Voice Live features. Here are the steps in detail:
## 1. Provision the Azure Voice Live API Resource
Voice Live is part of Azure’s Cognitive Services, under something called Azure AI Foundry. You will need to have an Azure subscription with access to the Voice Live API (currently in public preview as of mid-2025). Specifically, create an Azure AI Foundry resource in a supported region (e.g., `eastus` or `westus` – refer to Microsoft’s docs for the latest supported regions in the Voice Live overview). No custom model deployment is needed – the Voice Live models (GPT-4o, etc.) are provided out-of-the-box.
**Credentials:** Once you have the resource, note the endpoint URL and an API key (or set up Azure Entra ID authentication if you prefer token-based auth). The Voice Live endpoint will look like:
```
wss://.cognitiveservices.azure.com/voice-live/realtime?api-version=2025-05-01-preview&model=gpt-4o
```
This is the WebSocket URL to connect to the Voice Live API. We specify the model as a query parameter (`model=gpt-4o` or you could use `gpt-4o-mini-realtime-preview` for the smaller model). The API version `2025-05-01-preview` is the current one for this preview feature.
Make sure the resource’s "Keys and Endpoint" page in Azure portal gives you the correct hostname. If using API key authentication, you can pass the key in the connection as well. (For simplicity, we’ll use the API key in our example code. Azure also supports token auth with Entra ID which is more secure for production, but the key is fine for testing.)
## 2. Update Connection Code to Use Voice Live
In your backend (the RTMiddleTier in the sample app), you currently connect to the Azure OpenAI realtime endpoint (something like `wss://.openai.azure.com/openai/realtime?...deployment=gpt-4o-realtime-preview...`). You will replace that with the Voice Live endpoint from step 1.
**WebSocket Connection:** Use a WebSocket client to connect to the new URL. For example, in Python (as used by the repo), you might use the `websockets` library or `aiohttp`. Here’s a pseudo-code snippet illustrating the new connection setup:
```python
import asyncio, websockets, json
VOICE_LIVE_ENDPOINT = "wss://.cognitiveservices.azure.com/voice-live/realtime?api-version=2025-05-01-preview&model=gpt-4o"
API_KEY = ""
async def connect_voice_live():
# Include the API key in the query parameters or headers for authentication
url = VOICE_LIVE_ENDPOINT + f"&api-key={API_KEY}"
async with websockets.connect(url) as ws:
print("Connected to Azure Voice Live API")
# Step 3: configure session (send session.update)
session_config = {
"type": "session.update",
"session": {
"turn_detection": {
"type": "azure_semantic_vad",
"threshold": 0.3,
"silence_duration_ms": 200,
# Optionally fine-tune end_of_utterance_detection if needed
"end_of_utterance_detection": { "model": "semantic_detection_v1", "threshold": 0.01, "timeout": 2 }
},
"input_audio_noise_reduction": { "type": "azure_deep_noise_suppression" },
"input_audio_echo_cancellation": { "type": "server_echo_cancellation" },
"voice": { "name": "en-US-AriaNeural", "type": "azure-standard" }
}
}
await ws.send(json.dumps(session_config))
# ... (then you would send audio and handle responses as shown next)
```
In the above snippet, note a few things:
- We constructed the `VOICE_LIVE_ENDPOINT` with `model=gpt-4o`. To experiment with faster responses, you could set `model=gpt-4o-mini-realtime-preview`.
- We appended the API key in the URL (`&api-key=...`) for simplicity. Alternatively, you could do:
```python
ws = websockets.connect(VOICE_LIVE_ENDPOINT, extra_headers={"Authorization": "Bearer "})
```
if using an auth token.
- Once connected, we immediately prepare a `session.update` message (type `"session.update"`) to configure the conversation session.
## 3. Configure the Voice Live Session (Enable Noise Reduction, etc.)
After opening the WebSocket, the first message you send should be a `session.update` event to set up the desired behavior (if you omit this, defaults will apply – but we want to ensure noise suppression is on, etc.). In the code above, `session_config` is the JSON payload configuring:
- **Turn detection:** Here we chose `"azure_semantic_vad"` as discussed, with a moderate threshold (`0.3`) and requiring `200 ms` of silence to decide end-of-turn. We also included an `end_of_utterance_detection` with a very low threshold (`0.01`) and short timeout (`2 seconds`) – these values are inspired by Microsoft’s example configurations.
- **Noise reduction:** We set `"input_audio_noise_reduction": { "type": "azure_deep_noise_suppression" }` to turn on the DNS noise filter. This ensures background noise is suppressed.
- **Echo cancellation:** `"input_audio_echo_cancellation": { "type": "server_echo_cancellation" }` enables echo cancellation (so the agent’s voice playing on speakers won’t feed into the microphone).
- **Voice output:** The `"voice"` field specifies which TTS voice to use for responses. In our example, we used `"en-US-AriaNeural"` (Aria is a standard American English voice). You might choose a different one or a custom voice if you have one.
After sending this `session.update`, you should wait for a confirmation event (the server will reply with a `session.updated` message), indicating it accepted your config. In most implementations, you can proceed without explicitly waiting as long as subsequent events are handled asynchronously.
**Preserving RAG Tools:** Make sure the model knows about the knowledge base search tool. With GPT-4o realtime, you likely set up a function (e.g., `search()` function) that the model could call. In the Voice Live API, function calling is supported in a similar manner. You can include a `"tools"` list in the `session.update` payload describing the functions, or send a system message once the conversation starts. Replicate the same tool definitions and system instructions you used earlier so the model knows to use the knowledge base.
The VoiceRAG sample likely configured the search tool through the system prompt or session so that the model would call it when needed. Ensure you replicate that in the new setup. Aside from the audio-related settings, include the same tool definitions (and system instructions) you used earlier so the model knows to use the knowledge base. Voice Live’s compatibility means the model should invoke `knowledge_search` (or whatever it’s named) and you will receive a `function_call` event from the stream. Your backend logic for handling that call (performing the Azure Cognitive Search query and returning the results via a function result message) can remain almost the same as before.
**Note:** The Voice Live API *is designed for compatibility with the Azure OpenAI Realtime API events*, so the function call and response events should have the same structure. You shouldn’t need to rewrite the search-handling logic, just plug it into the new connection.
## 4. Stream Audio Input and Output
With the session configured, the main loop of your backend remains: send audio chunks from the user’s microphone to the API, and receive events (transcripts, responses, audio) back. In Voice Live, the sequence goes like:
- **Sending audio:** As the user speaks, your frontend likely sends audio packets to the backend. The backend should forward them to the Voice Live socket using `input_audio_buffer.append` messages. This is exactly analogous to how it was done for GPT-4o. Each message contains a chunk of audio (as binary or base64). For example:
```json
{ "type": "input_audio_buffer.append", "audio": "", "event_id": "" }
```
- **Automatic turn ending:** If you set `turn_detection.type = server_vad`, the service will automatically determine when to stop listening. When it decides the user is done (silence met), it will move to respond. In GPT-4o’s API, this triggered a `conversation.turn.end` or similar event. In Voice Live, you may get an event indicating end of input or it will simply start the response. (If you had set `turn_detection` to `none`, you would manually send an `input_audio_buffer.commit` and a `response.create` to initiate a response. But we are using the automated mode.)
- **Receiving the response:** The Voice Live API will start sending back the AI’s answer as a series of events. You will receive events for the content of the answer (text and/or audio) and eventually an audio stream. In practice, you’ll get something like:
- `conversation.response.started` (indicating the model began formulating a response),
- `conversation.response.item` events that carry either text or audio segments,
- `conversation.response.finished` when done.
Voice Live can send audio content parts directly, so you might get `content_part` events with audio. In the GPT-4o sample, likely the backend forwarded the audio bytes to the frontend to play via an audio element. You will do the same here. The format of these events is nearly the same as before, so your existing event handling code (that takes the incoming audio bytes from the socket and streams them out to the client) should work with minimal tweaks. Just ensure you adapt to any minor differences in field names if present.
- **Transcription (Optional):** If you want to display the recognized text of the user’s question (as the sample app shows the user query and citations on screen), you can use the transcription feature. In the `session.update`, set:
```json
"input_audio_transcription": { "model": "whisper-1" }
```
which would make the service send `conversation.item.audio_transcription` events containing the text it understood.
This is optional – you might already be doing transcription on the client or not displaying it. But Voice Live gives you the option to get the text without a separate call. The recognized text can be used for debugging or showing “You asked: _____” on the UI.
## 5. Test the End-to-End System
Run your modified application and test it thoroughly:
- Speak a question with background noise (for example, have music or chatter in the room) and verify that the system no longer gets triggered until you actually ask the question. It should wait for clear speech.
- Ask a question and see that the response is quick and the content is correct (the knowledge base lookup still works, and the answer is grounded with the info). Monitor the timing: you should observe that as soon as you finish speaking, the backend returns a `response.started` event almost immediately and audio starts playing back very shortly after.
- Try interrupting the AI mid-answer to ensure the interruption detection is working (if your app supports barge-in).
- Check that the voice output sounds good and there’s no echo (it shouldn’t, with echo cancellation on).
- Also test the edge cases: long pauses while asking something, speaking very softly or from a bit farther (to see if threshold needs tuning), multiple quick questions in succession, etc.
You may adjust the VAD settings based on testing. For instance, if you find the system sometimes cuts off the end of the user's question, you might increase `silence_duration_ms` or lower the threshold a bit. Or if it’s too slow to end turn, you might shorten the timeout. The defaults we used (`0.3` threshold, `0.2` sec silence) are a reasonable starting point.
## Code Integration Considerations
Since you already have a working pipeline with the OpenAI realtime model, integrating Voice Live should be mostly swapping endpoints and config as described. The existing code for capturing audio (likely using the browser Web Audio API), sending it, and playing the response audio remains the same. The backend logic for the search tool (function calling) remains the same. In fact, Microsoft notes that “any client that works directly against the Azure OpenAI API will just work against the real-time [Voice Live] middle tier” because the protocol is encapsulated similarly. This indicates that only minimal code changes are needed on your side.
One difference is how you authenticate: Azure OpenAI used a key or token on the OpenAI endpoint. For Voice Live (Cognitive Services), you use that resource’s key or token. Just be careful to use the correct credential for the new endpoint (don’t accidentally use the OpenAI API key on the cognitive services endpoint, it won’t authorize).
Finally, update any documentation or configuration files in your repo if needed (for example, `.env` files or environment variables). The sample might have environment variables like `OPENAI_ENDPOINT`, `OPENAI_KEY`, etc. You’d introduce perhaps `VOICE_LIVE_ENDPOINT` and `VOICE_LIVE_KEY` or similar and adjust the code to use those for the new mode.
---
By following these steps, you essentially replace the speech backend of your application with Voice Live, while keeping the RAG logic intact. The outcome should be a voice assistant that responds faster and handles noise gracefully, matching the improvements we discussed.
