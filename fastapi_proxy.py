import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse, JSONResponse, FileResponse

load_dotenv()  # 读取 .env 文件

BACKEND_URL = "http://172.16.10.27"
API_KEY = os.getenv("DIFY_REPORT_API_KEY")

app = FastAPI()
# 支持所有跨域请求
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def index():
    return "FastAPI 代理服务器运行中"

@app.get("/web")
def get_web_source():
    web_source = "static/report-audit.html"
    return FileResponse(web_source, media_type="text/html")

@app.get("/proxy/whoami")
async def proxy_whoami(request: Request):
    ip = request.headers.get("x-forwarded-for")
    if not ip:
        ip = request.client.host
    print(f"[{datetime.now().isoformat()}] whoami 请求，IP: {ip}")
    return {"ip": ip}


@app.post("/proxy/files/upload")
async def proxy_upload(
    request: Request,
    file: UploadFile = File(...),
    user: str = Form("unknown-user"),
):
    ip = request.headers.get("x-forwarded-for")
    if not ip:
        ip = request.client.host

    if not file:
        print(f"[{datetime.now().isoformat()}] ⛔ 上传失败（无文件） - IP: {ip}")
        raise HTTPException(status_code=415, detail="请求中没有文件，确保未手动设置Content-Type")

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    data = await request.form()
    data_dict = dict(data)

    print(f"[{datetime.now().isoformat()}] 📥 文件上传请求")
    print(f"  ➤ 用户: {user}")
    print(f"  ➤ IP: {ip}")
    print(f"  ➤ 文件名: {file.filename}")
    print(f"  ➤ 文件类型: {file.content_type}")
    # 上传文件大小未知，FastAPI没有直接属性
    print(f"  ➤ 表单字段: {data_dict}")

    # 把文件流传给后端
    try:
        resp = requests.post(
            f"{BACKEND_URL}/v1/files/upload",
            headers=headers,
            files={"file": (file.filename, file.file, file.content_type)},
            data=data_dict,
        )
        print(f"  ✅ 转发成功，状态码: {resp.status_code}")
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("Content-Type"))
    except Exception as e:
        print(f"  ❌ 转发失败: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/proxy/chat-messages")
async def proxy_chat(request: Request):
    ip = request.headers.get("x-forwarded-for")
    if not ip:
        ip = request.client.host

    payload = await request.json()
    user = payload.get("user", "unknown-user")
    query = payload.get("query", "")
    rule_file_id = payload.get("inputs", {}).get("rule_file", {}).get("upload_file_id", "no-rule-file")
    detect_file_id = "no-detect-file"
    files_list = payload.get("files", [])
    if isinstance(files_list, list) and len(files_list) > 0:
        detect_file_id = files_list[0].get("upload_file_id", "no-detect-file")

    print(f"[{datetime.now().isoformat()}] 📤 审查请求")
    print(f"  ➤ 用户: {user}")
    print(f"  ➤ IP: {ip}")
    print(f"  ➤ query: {query}")
    print(f"  ➤ 规则文件 ID: {rule_file_id}")
    print(f"  ➤ 检测单文件 ID: {detect_file_id}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{BACKEND_URL}/v1/chat-messages",
            headers=headers,
            json=payload,
            stream=True,
        )
        print(f"  ✅ 转发成功，状态码: {resp.status_code}")

        def generate():
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk

        return StreamingResponse(generate(), media_type=resp.headers.get("Content-Type"))
    except Exception as e:
        print(f"  ❌ 转发失败: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    print(f"🚀 FastAPI 服务启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=9000)

'''
nohup python -u fastapi_proxy.py > fastapi.log 2>&1 &
'''


