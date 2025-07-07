import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()  # 读取当前目录下的 .env 文件

BACKEND_URL = "http://172.16.10.27"
API_KEY = os.getenv("DIFY_REPORT_API_KEY")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
CORS(app)  # 启用所有路由的 CORS 支持

@app.route("/")
def index():
    return "Flask 代理服务器运行中"

@app.route("/web")
def get_web_source():
    web_source = "static/report-audit.html"
    return send_file(web_source, mimetype="text/html")

@app.route('/proxy/whoami')
def proxy_whoami():
    # 尝试从 X-Forwarded-For 获取真实 IP（如果部署在反向代理后）
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    print(f"[{datetime.now().isoformat()}] whoami 请求，IP: {ip}")
    ip_data = jsonify({"ip": ip})
    return ip_data

@app.route('/proxy/files/upload', methods=['POST'])
def proxy_upload():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if 'file' not in request.files:
        print(f"[{datetime.now().isoformat()}] ⛔ 上传失败（无文件） - IP: {ip}")
        return jsonify({'error': '请求中没有文件，确保未手动设置Content-Type'}), 415
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    file = request.files['file']  # ✅ 直接取文件对象
    files = {
        'file': (file.filename, file.stream, file.content_type)
    }
    user = request.form.get('user', 'unknown-user')
    data = request.form.to_dict()
    # 打印请求日志
    print(f"[{datetime.now().isoformat()}] 📥 文件上传请求")
    print(f"  ➤ 用户: {user}")
    print(f"  ➤ IP: {ip}")
    print(f"  ➤ 文件名: {file.filename}")
    print(f"  ➤ 文件类型: {file.content_type}")
    print(f"  ➤ 文件大小: {file.content_length or '未知'}")
    print(f"  ➤ 表单字段: {data}")
    try:
        resp = requests.post(f"{BACKEND_URL}/v1/files/upload", headers=headers, files=files, data=data)
        print(f"  ✅ 转发成功，状态码: {resp.status_code}")
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
    except Exception as e:
        print(f"  ❌ 转发失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/proxy/chat-messages', methods=['POST'])
def proxy_chat():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    # 获取 JSON 请求体
    payload = request.get_json(force=True) or {}
    user = payload.get('user', 'unknown-user')
    query = payload.get('query', '')
    rule_file_id = payload.get('inputs', {}).get('rule_file', {}).get('upload_file_id', 'no-rule-file')
    detect_file_id = payload.get('files', {})[0].get('upload_file_id', 'no-detect-file')
    # 打印详细日志
    print(f"[{datetime.now().isoformat()}] 📤 审查请求")
    print(f"  ➤ 用户: {user}")
    print(f"  ➤ IP: {ip}")
    print(f"  ➤ query: {query}")
    print(f"  ➤ 规则文件 ID: {rule_file_id}")
    print(f"  ➤ 检测单文件 ID: {detect_file_id}")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/v1/chat-messages",
            headers=headers,
            json=payload,
            stream=True
        )
        print(f"  ✅ 转发成功，状态码: {resp.status_code}")
        def generate():
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        return Response(generate(), content_type=resp.headers.get('Content-Type'))
    except Exception as e:
        print(f"  ❌ 转发失败: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    print(f"🚀 Flask 服务启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    app.run(host="0.0.0.0", port=9001)

'''
nohup python -u flask_proxy.py > flask.log 2>&1 &
'''


