from flask import Flask, request, Response, jsonify
import requests
import json
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_API_KEY = "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"  # Replace with actual key

MAX_RETRIES = 3
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 300

@app.route('/v1/chat/completions', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/chat/completions', methods=['GET', 'POST', 'OPTIONS'])
def chat_completions():
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response, 200

    if request.method == 'GET':
        return jsonify({"status": "active", "message": "NVIDIA Proxy Connected!"})

    data = request.json or {}
    messages = data.get("messages", [])

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }

    model_name = data.get("model", "deepseek-ai/deepseek-v4.1-flash")

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 1024),
        "stream": True
    }

    def generate():
        r = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.post(
                    NVIDIA_API_URL,
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
                )
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'connection_error'}})}\n\n"
                    return
                time.sleep(1)

        if r is None or r.status_code != 200:
            status = r.status_code if r else 500
            yield f"data: {json.dumps({'error': {'message': f'NVIDIA API returned {status}'}})}\n\n"
            return

        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                content = line[6:].strip()
                if content == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                try:
                    parsed = json.loads(content)
                    chunk = {
                        "id": parsed.get("id", "chatcmpl-stream"),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": parsed.get("choices", [])
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                except json.JSONDecodeError:
                    continue

    resp = Response(generate(), mimetype='text/event-stream')
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
