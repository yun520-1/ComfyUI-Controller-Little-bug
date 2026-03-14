#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI Web 服务器
提供 Web 界面和 API 来控制 ComfyUI
"""

from flask import Flask, send_from_directory, request, jsonify
import requests
import websocket
import json
import uuid
import threading
import time

app = Flask(__name__)

COMFYUI_SERVER = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

@app.route('/')
def index():
    """提供 Web 界面"""
    return send_from_directory('.', 'index.html')

@app.route('/system_stats')
def system_stats():
    """代理系统状态"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/queue')
def queue():
    """代理队列状态"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/queue", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/prompt', methods=['POST'])
def prompt():
    """提交提示词到 ComfyUI"""
    try:
        data = request.json
        resp = requests.post(
            f"http://{COMFYUI_SERVER}/prompt",
            json=data,
            timeout=10
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history/<prompt_id>')
def history(prompt_id):
    """获取历史记录"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view')
def view():
    """代理图片查看"""
    try:
        params = request.args
        resp = requests.get(
            f"http://{COMFYUI_SERVER}/view",
            params=params,
            timeout=30
        )
        return resp.content, 200, {'Content-Type': resp.headers.get('Content-Type', 'image/png')}
    except Exception as e:
        return str(e), 500

@app.route('/object_info/<node_class>')
def object_info(node_class):
    """获取节点信息"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/object_info/{node_class}", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ws')
def ws():
    """WebSocket 代理（简化版本，实际需要使用 WebSocket 库）"""
    return jsonify({"status": "WebSocket not proxied, connect directly to ComfyUI"})

if __name__ == '__main__':
    print("🎨 ComfyUI Web 服务器启动中...")
    print(f"   访问地址：http://0.0.0.0:5005")
    print(f"   ComfyUI:  {COMFYUI_SERVER}")
    app.run(host='0.0.0.0', port=5005, debug=False)
