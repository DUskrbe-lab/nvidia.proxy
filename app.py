from flask import Flask, request, Response, jsonify
import requests
import json
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------------------
# CONFIG
# ---------------------------
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_API_KEY = "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"   # <-- replace with your actual key

# Retry settings
MAX_RETRIES = 3
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 300

# ---------------------------
# MAIN ROUTE
# ---------------------------
@app.route('/v1/chat/completions', methods=['GET', 'POST', 'OPTIONS'])
def chat_completions():
    print(f"🎯 Received {request.method} request")

    if request.method == 'GET':
        return jsonify({"status": "active", "message": "NVIDIA Proxy Connected!"})

    if request.method == 'OPTIONS':
        return '', 200

    print("📤 Janitor AI POST request received!")

    try:
        data = request.json.copy()
        messages = data.get("messages", [])
        user_message = messages[-1].get("content", "Hello") if messages else "Hello"
        print(f"💬 User message: {user_message}")

        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        }

        # ✅ HERE IS THE KEY CHANGE – model set to deepseek-v4-flash
        payload = {
            "model": "deepseek-ai/deepseek-v4.1-flash",
            "messages": messages,
            "temperature": data.get("temperature", 0.7),
            "max_tokens": data.get("max_tokens", 1024),
            "stream": True
        }

        def generate():
            print("🚀 Initializing NVIDIA streaming request...")
            r = None

            for attempt in range(1, MAX_RETRIES + 1):
                print(f"🔄 Attempt {attempt} to connect to NVIDIA...")
                try:
                    r = requests.post(
                        NVIDIA_API_URL,
                        headers=headers,
                        json=payload,
                        stream=True,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
                    )
                    break
                except requests.exceptions.Timeout:
                    print(f"⏰ Connect timeout on attempt {attempt}")
                    if attempt == MAX_RETRIES:
                        yield f"data: {json.dumps({'error': {'message': 'NVIDIA API timeout', 'type': 'timeout_error'}})}\n\n"
                        return
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ Connect error: {e}")
                    if attempt == MAX_RETRIES:
                        yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'connection_error'}})}\n\n"
                        return
                    time.sleep(1)

            if r is None:
                yield f"data: {json.dumps({'error': {'message': 'Failed to connect to NVIDIA API', 'type': 'connection_error'}})}\n\n"
                return

            if r.status_code != 200:
                print(f"❌ NVIDIA returned HTTP {r.status_code}")
                try:
                    error_details = r.json()
                except:
                    error_details = r.text
                yield f"data: {json.dumps({'error': {'message': f'NVIDIA API returned {r.status_code}', 'details': error_details}})}\n\n"
                return

            print("🚀 NVIDIA connection established — beginning streaming...")
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:].strip()
                if line == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    print(f"⚠️ Bad JSON chunk: {line[:60]}...")
                    continue
                chunk = {
                    "id": parsed.get("id", "stream"),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": parsed.get("model", "deepseek-ai/deepseek-v4-flash"),
                    "choices": parsed.get("choices", [])
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            print("✅ Streaming complete.")

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"❌ Proxy error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 NVIDIA Streaming Proxy (deepseek-v4-flash) running on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
