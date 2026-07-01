import os
import json
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

node_name = os.getenv('NODE_NAME', 'Unknown-Node')
node_ip = os.getenv('NODE_IP', 'Unknown-IP')

CONFIG_PATH = '/app/config/worker_nodes.json'

def load_target_nodes():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                return f.read().strip()
    except Exception as e:
        print(f"ConfigMap load error: {e}")
    return "[]"

nodes_json_data = load_target_nodes()

# f-string을 제거하고 일반 multi-line string으로 변경하여 JS 중괄호 충돌 완전 방지
html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>셀프 텔넷 대시보드</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f6f9; }
        .container { max-width: 850px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; margin-bottom: 5px; }
        .node-info { text-align: center; color: #666; margin-bottom: 30px; font-size: 14px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        button { width: 100%; padding: 12px; background-color: #2eb85c; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; font-weight: bold; }
        button:hover { background-color: #1b943e; }
        .result-box { margin-top: 30px; display: none; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f8f9fa; }
        .SUCCESS { color: green; font-weight: bold; }
        .FAILED { color: red; font-weight: bold; }
        .loading { text-align: center; font-weight: bold; color: #666; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Self Telnet Dashboard</h2>
        <div class="node-info">현재 브라우저 접속 노드: <b>{__NODE_NAME__}</b> ({__NODE_IP__})</div>
        <div class="form-group">
            <label>목적지 IP / Domain</label>
            <input type="text" id="target_ip" placeholder="예: 1.1.1.1 또는 google.com">
        </div>
        <div class="form-group">
            <label>목적지 Port</label>
            <input type="text" id="target_port" placeholder="예: 8080">
        </div>
        <button onclick="checkAllNodesFirewall()">전체 노드 일괄 테스트 실행</button>
        <div class="loading" id="loading">모든 워커 노드에서 동시 점검 중입니다...</div>
        <div class="result-box" id="result_box">
            <h3>클러스터 전수 조사 결과</h3>
            <table>
                <thead>
                    <tr><th>테스트 실행 노드</th><th>통신 결과</th><th>상세 로그 (open 검증)</th></tr>
                </thead>
                <tbody id="result_body"></tbody>
            </table>
        </div>
    </div>
    <script>
        const nodeWebsites = {__NODES_JSON_DATA__};

        async function checkAllNodesFirewall() {
            const ip = document.getElementById('target_ip').value;
            const port = document.getElementById('target_port').value;
            if(!ip || !port) { alert('IP와 Port를 모두 입력해주세요.'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result_box').style.display = 'none';
            document.getElementById('result_body').innerHTML = '';

            const requests = nodeWebsites.map(async (node) => {
                try {
                    const controller = new AbortController();
                    const id = setTimeout(() => controller.abort(), 3500);

                    const res = await fetch(`http://${node.ip}:30003/run-check?ip=${encodeURIComponent(ip)}&port=${encodeURIComponent(port)}`, { signal: controller.signal });
                    clearTimeout(id);
                    
                    if (!res.ok) throw new Error();
                    return await res.json();
                } catch (e) {
                    return { 
                        node: `${node.name} (${node.ip})`, 
                        status: "FAILED", 
                        detail: "에이전트 응답 없음 또는 네트워크 차단" 
                    };
                }
            });

            const results = await Promise.all(requests);
            
            let rows = '';
            results.forEach(data => {
                rows += `<tr>
                    <td><b>${data.node}</b></td>
                    <td class='${data.status}'>${data.status}</td>
                    <td><code>${data.detail || 'Connected'}</code></td>
                </tr>`;
            });
            
            document.getElementById('result_body').innerHTML = rows;
            document.getElementById('loading').style.display = 'none';
            document.getElementById('result_box').style.display = 'block';
        }
    </script>
</body>
</html>
""".replace("{__NODE_NAME__}", node_name).replace("{__NODE_IP__}", node_ip).replace("{__NODES_JSON_DATA__}", nodes_json_data)

class CombinedHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        if url_parts.path == '/run-check':
            query = urllib.parse.parse_qs(url_parts.query)
            tip = query.get('ip', [''])[0]
            tport = query.get('port', [''])[0]
            
            cmd = f'nc -zv -w 3 {tip} {tport}'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            status = 'SUCCESS' if res.returncode == 0 else 'FAILED'
            output = res.stderr if res.stderr else res.stdout
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'node': f"{node_name} ({node_ip})", 'status': status, 'detail': output.strip()}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))

print('ConfigMap-Driven Telnet Dashboard Started...')
HTTPServer(('0.0.0.0', 8080), CombinedHandler).serve_forever()
