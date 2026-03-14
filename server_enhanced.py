#!/usr/bin/env python3
# -*- utf-8 -*-
"""
ComfyUI Web 服务器 - 增强版
功能：
- Web 界面
- API 代理
- WebSocket 支持（使用 flask-socketio）
- 工作流上传
- 批量任务管理
"""

from flask import Flask, send_from_directory, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import requests
import websocket
import json
import uuid
import threading
import time
import os
from pathlib import Path
from workflow_manager import WorkflowManager
from auto_workflow_runner import AutoWorkflowRunner

app = Flask(__name__)
app.config['SECRET_KEY'] = 'comfyui-controller-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

COMFYUI_SERVER = "127.0.0.1:8188"
client_id = str(uuid.uuid4())
workflow_manager = WorkflowManager()
auto_runner = AutoWorkflowRunner(COMFYUI_SERVER)

# 全局任务状态
task_status = {}


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


# ============ 工作流管理 API ============

@app.route('/api/workflows', methods=['GET'])
def api_list_workflows():
    """列出所有工作流"""
    category = request.args.get('category')
    workflows = workflow_manager.list_workflows(category)
    return jsonify({"workflows": workflows})


@app.route('/api/workflows', methods=['POST'])
def api_upload_workflow():
    """上传工作流"""
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400
    
    file = request.files['file']
    name = request.form.get('name', file.filename)
    category = request.form.get('category', 'custom')
    description = request.form.get('description', '')
    
    # 保存临时文件
    temp_path = Path(f"/tmp/{file.filename}")
    file.save(temp_path)
    
    result = workflow_manager.upload_workflow(
        str(temp_path),
        name=name,
        category=category,
        description=description
    )
    
    # 清理临时文件
    temp_path.unlink()
    
    return jsonify(result)


@app.route('/api/workflows/<workflow_id>', methods=['GET'])
def api_get_workflow(workflow_id):
    """获取工作流详情"""
    workflow = workflow_manager.get_workflow(workflow_id)
    if workflow:
        return jsonify(workflow)
    return jsonify({"error": "工作流不存在"}), 404


@app.route('/api/workflows/<workflow_id>', methods=['DELETE'])
def api_delete_workflow(workflow_id):
    """删除工作流"""
    result = workflow_manager.delete_workflow(workflow_id)
    return jsonify(result)


@app.route('/api/workflows/<workflow_id>/execute', methods=['POST'])
def api_execute_workflow(workflow_id):
    """执行工作流"""
    data = request.json or {}
    prompt = data.get('prompt')
    negative = data.get('negative')
    steps = data.get('steps', 20)
    cfg = data.get('cfg', 7)
    width = data.get('width', 512)
    height = data.get('height', 512)
    
    result = auto_runner.run_workflow(
        workflow_id,
        prompt=prompt,
        negative=negative,
        steps=steps,
        cfg=cfg,
        width=width,
        height=height
    )
    
    return jsonify(result)


# ============ WebSocket 支持 ============

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print(f"🔌 客户端已连接: {request.sid}")
    emit('connected', {'client_id': client_id})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print(f"🔌 客户端已断开：{request.sid}")


@socketio.on('monitor_task')
def handle_monitor_task(data):
    """监控任务进度"""
    prompt_id = data.get('prompt_id')
    task_status[prompt_id] = {'status': 'running', 'progress': 0}
    
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}", timeout=10)
        
        while True:
            msg = json.loads(ws.recv())
            msg_type = msg.get('type')
            msg_data = msg.get('data', {})
            
            if msg_type == 'progress':
                step = msg_data.get('value', 0)
                total = msg_data.get('max', 100)
                percent = int(step / total * 100)
                task_status[prompt_id] = {'status': 'running', 'progress': percent}
                emit('progress', {'prompt_id': prompt_id, 'step': step, 'total': total, 'percent': percent})
            
            elif msg_type == 'executing':
                if msg_data.get('node') is None:
                    task_status[prompt_id] = {'status': 'completed', 'progress': 100}
                    emit('completed', {'prompt_id': prompt_id})
                    break
            
            elif msg_type == 'execution_error':
                task_status[prompt_id] = {'status': 'error', 'error': msg_data.get('message')}
                emit('error', {'prompt_id': prompt_id, 'error': msg_data.get('message')})
                break
        
        ws.close()
    except Exception as e:
        task_status[prompt_id] = {'status': 'error', 'error': str(e)}
        emit('error', {'prompt_id': prompt_id, 'error': str(e)})


@socketio.on('check_connection')
def handle_check_connection():
    """检查 ComfyUI 连接"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        emit('connection_status', {'connected': True, 'stats': resp.json()})
    except Exception as e:
        emit('connection_status', {'connected': False, 'error': str(e)})


# ============ 批量任务 API ============

@app.route('/api/batch', methods=['POST'])
def api_batch_execute():
    """批量执行任务"""
    data = request.json
    workflow_ids = data.get('workflow_ids', [])
    prompts = data.get('prompts', [])
    params = data.get('params', {})
    
    if not workflow_ids:
        return jsonify({"error": "没有指定工作流"}), 400
    
    # 在后台线程中执行
    def run_batch():
        results = auto_runner.batch_run(
            workflow_ids,
            prompts=prompts if prompts else None,
            **params
        )
        # 通过 WebSocket 通知完成
        socketio.emit('batch_completed', {'results': results})
    
    thread = threading.Thread(target=run_batch)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "count": len(workflow_ids)})


@app.route('/api/task_status/<prompt_id>')
def api_task_status(prompt_id):
    """获取任务状态"""
    status = task_status.get(prompt_id, {'status': 'unknown'})
    return jsonify(status)


if __name__ == '__main__':
    print("\n🎨 ComfyUI Web 服务器（增强版）启动中...")
    print(f"   访问地址：http://0.0.0.0:5005")
    print(f"   ComfyUI:  http://{COMFYUI_SERVER}")
    print(f"   WebSocket: ws://0.0.0.0:5005/socket.io")
    print(f"   客户端 ID: {client_id}")
    print("\n按 Ctrl+C 停止服务器\n")
    
    # 使用 socketio 运行（支持 WebSocket）
    socketio.run(app, host='0.0.0.0', port=5005, debug=False, allow_unsafe_werkzeug=True)
