#!/usr/bin/env python3
"""
AI模型识别器后端代理服务器
解决浏览器 CORS 限制，代理所有 API 请求
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import json
import re
import time
import requests as req_lib
import os
import webbrowser
import threading
import uuid
import platform
import sys
import importlib.util
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = '2.4.0-integrated.1'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ========================================
#  请求头伪装预设 (全小写 key，匹配真实 Node.js SDK)
# ========================================
_STAINLESS_OS = {
    'Darwin': 'MacOS', 'Linux': 'Linux', 'Windows': 'Windows'
}.get(platform.system(), f'Other:{platform.system()}')

_STAINLESS_ARCH = {
    'x86_64': 'x64', 'AMD64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64',
    'x86': 'x32', 'i386': 'x32', 'i686': 'x32',
}.get(platform.machine(), f'other:{platform.machine()}')

# Codex 安装 ID — 进程生命周期内固定
_CODEX_INSTALLATION_ID = str(uuid.uuid4())

HEADER_PRESETS = {
    'claude-code': {
        'accept': 'application/json',
        'accept-encoding': 'gzip, deflate, br',
        'connection': 'keep-alive',
        'user-agent': 'Anthropic/JS 0.109.0',
        'x-stainless-lang': 'js',
        'x-stainless-package-version': '0.109.0',
        'x-stainless-os': _STAINLESS_OS,
        'x-stainless-arch': _STAINLESS_ARCH,
        'x-stainless-runtime': 'node',
        'x-stainless-runtime-version': 'v22.13.1',
        'x-stainless-retry-count': '0',
    },
    'codex': {
        'accept': 'application/json',
        'accept-encoding': 'gzip, deflate, br',
        'connection': 'keep-alive',
        'user-agent': 'OpenAI/JS 6.45.0',
        'x-stainless-lang': 'js',
        'x-stainless-package-version': '6.45.0',
        'x-stainless-os': _STAINLESS_OS,
        'x-stainless-arch': _STAINLESS_ARCH,
        'x-stainless-runtime': 'node',
        'x-stainless-runtime-version': 'v22.13.1',
        'x-stainless-retry-count': '0',
        'openai-beta': 'responses_websockets=2026-02-06',
        'x-codex-installation-id': _CODEX_INSTALLATION_ID,
    },
}

# 默认浏览器伪装头
DEFAULT_BROWSER_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'accept-language': 'en-US,en;q=0.9',
    'connection': 'keep-alive',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

# 创建全局 Session，清除默认头，避免泄漏 python-requests 指纹
_session = req_lib.Session()
_session.headers.clear()

# ========================================
#  可选能力评测任务（EvalScope）
# ========================================
CAPABILITY_DATASETS = {
    'iquiz': 'IQ / EQ 综合题',
    'gsm8k': '小学数学推理',
    'mmlu': '多学科知识',
    'mmlu_pro': '高难度多学科知识',
    'gpqa_diamond': '研究生级科学推理',
    'math_500': '数学推理',
    'ifeval': '指令遵循',
    'general_fc': '工具调用',
}
_capability_jobs = {}
_capability_jobs_lock = threading.Lock()
_capability_processes = {}
_CAPABILITY_MAX_OUTPUT = 30000


def _capability_runtime_root():
    """Keep optional evaluation artifacts outside the repository."""
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        root = os.path.join(os.environ['LOCALAPPDATA'], 'AI-Dev-Bootstrap', 'ModelIntegrityCheckerRuntime')
    else:
        root = os.path.join(os.path.expanduser('~'), '.cache', 'llm-integrity-checker')
    os.makedirs(root, exist_ok=True)
    return root


def _capability_engine_status():
    installed = importlib.util.find_spec('evalscope') is not None
    version = None
    if installed:
        try:
            from evalscope.version import __version__
            version = __version__
        except Exception:
            version = 'unknown'
    return {
        'installed': installed,
        'version': version,
        'datasets': [{'id': key, 'name': value} for key, value in CAPABILITY_DATASETS.items()],
        'install_script': 'scripts/Install-Capability-Engine.ps1',
        'upstream': 'https://github.com/modelscope/evalscope',
    }


def _redact_secret(value, secret):
    if not secret or len(secret) < 8:
        return value
    return value.replace(secret, '[REDACTED]')


def _run_capability_job(job_id, config, api_key):
    runtime_root = _capability_runtime_root()
    jobs_dir = os.path.join(runtime_root, 'capability-jobs')
    output_dir = os.path.join(runtime_root, 'capability-results', job_id)
    os.makedirs(jobs_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    job_file = os.path.join(jobs_dir, f'{job_id}.json')

    with open(job_file, 'w', encoding='utf-8') as handle:
        json.dump({**config, 'work_dir': output_dir}, handle, ensure_ascii=False)

    runner = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'scripts', 'evalscope_runner.py'))
    env = os.environ.copy()
    env['LLM_INTEGRITY_EVAL_API_KEY'] = api_key
    output = []
    try:
        with _capability_jobs_lock:
            if _capability_jobs.get(job_id, {}).get('status') == 'stopping':
                _capability_jobs[job_id].update({
                    'status': 'stopped',
                    'output_dir': output_dir,
                    'finished_at': time.time(),
                })
                return
        process = subprocess.Popen(
            [sys.executable, runner, job_file],
            cwd=os.path.dirname(runner),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        with _capability_jobs_lock:
            _capability_jobs[job_id].update({'status': 'running', 'pid': process.pid})
            _capability_processes[job_id] = process

        for line in process.stdout or ():
            clean = _redact_secret(line.rstrip(), api_key)
            if clean:
                output.append(clean)
                output[:] = output[-160:]
            with _capability_jobs_lock:
                _capability_jobs[job_id]['output'] = '\n'.join(output)[-_CAPABILITY_MAX_OUTPUT:]

        return_code = process.wait()
        with _capability_jobs_lock:
            job = _capability_jobs[job_id]
            job.update({
                'status': 'stopped' if job.get('status') == 'stopping' else ('completed' if return_code == 0 else 'failed'),
                'exit_code': return_code,
                'output': _redact_secret('\n'.join(output)[-_CAPABILITY_MAX_OUTPUT:], api_key),
                'output_dir': output_dir,
                'finished_at': time.time(),
            })
    except Exception as exc:
        with _capability_jobs_lock:
            _capability_jobs[job_id].update({
                'status': 'failed',
                'error': _redact_secret(str(exc), api_key),
                'finished_at': time.time(),
            })
    finally:
        with _capability_jobs_lock:
            _capability_processes.pop(job_id, None)
        try:
            os.remove(job_file)
        except OSError:
            pass


def _validate_capability_config(payload):
    if not isinstance(payload, dict):
        raise ValueError('请求体必须是 JSON 对象')
    eval_type = str(payload.get('eval_type', 'openai_api')).strip()
    if eval_type not in ('openai_api', 'openai_responses_api'):
        raise ValueError('不支持的 API 类型')
    api_url = str(payload.get('api_url', '')).strip().rstrip('/')
    model = str(payload.get('model', '')).strip()
    api_key = str(payload.get('api_key', '')).strip()
    if not api_url.startswith(('http://', 'https://')) or len(api_url) > 500:
        raise ValueError('API URL 必须是有效的 http(s) 地址')
    if eval_type in ('openai_api', 'openai_responses_api'):
        api_url = _normalize_openai_base_url(api_url)
    if not model or len(model) > 200:
        raise ValueError('模型名称不能为空且不能超过 200 个字符')
    if not api_key:
        raise ValueError('API Key 不能为空')
    datasets = payload.get('datasets', ['iquiz', 'gsm8k', 'mmlu'])
    if not isinstance(datasets, list):
        raise ValueError('datasets 必须是数组')
    datasets = list(dict.fromkeys(str(item).strip() for item in datasets))
    invalid = [item for item in datasets if item not in CAPABILITY_DATASETS]
    if invalid or not datasets:
        raise ValueError(f'不支持的数据集: {", ".join(invalid) or "空"}')
    try:
        limit = int(payload.get('limit', 10))
        concurrency = int(payload.get('concurrency', 1))
        max_tokens = int(payload.get('max_tokens', 2048))
    except (TypeError, ValueError):
        raise ValueError('样本数、并发数和最大输出长度必须是整数')
    if not 1 <= limit <= 200:
        raise ValueError('样本数范围为 1-200')
    if not 1 <= concurrency <= 8:
        raise ValueError('并发数范围为 1-8')
    if not 64 <= max_tokens <= 4096:
        raise ValueError('最大输出长度范围为 64-4096')
    return {
        'api_url': api_url,
        'model': model,
        'datasets': datasets,
        'limit': limit,
        'concurrency': concurrency,
        'max_tokens': max_tokens,
        'timeout': 120,
        'eval_type': eval_type,
    }, api_key


# ========================================
#  一键鉴别 — 官方基准仓库
# ========================================
GITHUB_OWNER  = 'hanlinwenyuan'
GITHUB_REPO   = 'hlwy-ai-checker'
GITHUB_BRANCH = 'main'
BASELINE_DIR  = 'baselines'

# 缓存 TTL（秒）— 避免频繁请求 GitHub 触发匿名 API 限流 (60 次/小时)
BASELINE_LIST_TTL = 300     # 模型列表缓存 5 分钟
BASELINE_FILE_TTL = 1800    # 单个基准文件缓存 30 分钟

_baseline_cache = {'list': None, 'list_source': '', 'list_ts': 0.0, 'files': {}}
_baseline_lock  = threading.Lock()

# 合法基准文件名（防止路径穿越 / URL 注入）
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._\-]{0,80}$')

# 拉取 GitHub 用的独立 Session：不带 accept-encoding，避免 zstd 等压缩解码失败
_gh_session = req_lib.Session()
_gh_session.headers.clear()

GITHUB_HEADERS = {
    'accept': 'application/vnd.github+json, application/json, */*',
    'accept-language': 'en-US,en;q=0.9',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}


def _gh_get(url, timeout=15):
    """带伪装头的 GET，返回解析后的 JSON"""
    resp = _gh_session.get(url, headers=GITHUB_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _normalize_openai_base_url(value):
    """Accept both provider roots and OpenAI-compatible /v1 base URLs."""
    base_url = (value or '').strip().rstrip('/')
    if not base_url:
        return base_url
    if not re.search(r'/v\d+(?:\.\d+)?$', base_url, re.IGNORECASE):
        base_url += '/v1'
    return base_url


def fetch_baseline_list(force=False):
    """
    获取 baselines 目录下的全部模型。
    源 1: GitHub Contents API   源 2: jsDelivr（国内可用性更好）
    返回 (models, source)，models 形如 [{'id':..., 'file':..., 'size':...}]
    """
    now = time.time()
    with _baseline_lock:
        cached = _baseline_cache['list']
        if not force and cached and (now - _baseline_cache['list_ts']) < BASELINE_LIST_TTL:
            return cached, _baseline_cache['list_source'] + '(缓存)'

    errors = []

    # ---- 源 1: GitHub Contents API ----
    try:
        data = _gh_get(
            f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}'
            f'/contents/{BASELINE_DIR}?ref={GITHUB_BRANCH}'
        )
        models = [
            {'id': it['name'][:-5], 'file': it['name'], 'size': it.get('size', 0)}
            for it in data
            if it.get('type') == 'file'
            and it.get('name', '').endswith('.json')
            and _SAFE_NAME_RE.match(it['name'][:-5] or '')
        ]
        if models:
            return _store_list(models, 'GitHub')
        errors.append('GitHub API: baselines 目录为空')
    except Exception as e:
        errors.append(f'GitHub API: {e}')

    # ---- 源 2: jsDelivr ----
    try:
        data = _gh_get(
            f'https://data.jsdelivr.com/v1/packages/gh/{GITHUB_OWNER}/'
            f'{GITHUB_REPO}@{GITHUB_BRANCH}?structure=flat'
        )
        prefix = f'/{BASELINE_DIR}/'
        models = []
        for it in data.get('files', []):
            name = it.get('name', '')
            if not name.startswith(prefix) or not name.endswith('.json'):
                continue
            stem = name[len(prefix):-5]
            if '/' in stem or not _SAFE_NAME_RE.match(stem):
                continue
            models.append({'id': stem, 'file': stem + '.json', 'size': it.get('size', 0)})
        if models:
            return _store_list(models, 'jsDelivr')
        errors.append('jsDelivr: baselines 目录为空')
    except Exception as e:
        errors.append(f'jsDelivr: {e}')

    # 全部失败：如果有过期缓存，降级返回，总比什么都没有强
    with _baseline_lock:
        if _baseline_cache['list']:
            return _baseline_cache['list'], _baseline_cache['list_source'] + '(过期缓存)'

    raise RuntimeError('；'.join(errors))


def _store_list(models, source):
    models.sort(key=lambda m: m['id'].lower())
    with _baseline_lock:
        _baseline_cache['list']        = models
        _baseline_cache['list_source'] = source
        _baseline_cache['list_ts']     = time.time()
    return models, source


def fetch_baseline_file(name, force=False):
    """下载单个基准文件，raw.githubusercontent 失败时回落 jsDelivr。返回 (data, source)"""
    if not _SAFE_NAME_RE.match(name):
        raise ValueError('基准名称不合法')

    now = time.time()
    with _baseline_lock:
        hit = _baseline_cache['files'].get(name)
        if not force and hit and (now - hit['ts']) < BASELINE_FILE_TTL:
            return hit['data'], hit['source'] + '(缓存)'

    errors = []
    sources = [
        ('GitHub', f'https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}'
                   f'/{GITHUB_BRANCH}/{BASELINE_DIR}/{name}.json'),
        ('jsDelivr', f'https://cdn.jsdelivr.net/gh/{GITHUB_OWNER}/{GITHUB_REPO}'
                     f'@{GITHUB_BRANCH}/{BASELINE_DIR}/{name}.json'),
    ]

    for source, url in sources:
        try:
            data = _gh_get(url, timeout=20)
            with _baseline_lock:
                _baseline_cache['files'][name] = {'data': data, 'source': source, 'ts': time.time()}
            return data, source
        except Exception as e:
            errors.append(f'{source}: {e}')

    with _baseline_lock:
        hit = _baseline_cache['files'].get(name)
        if hit:
            return hit['data'], hit['source'] + '(过期缓存)'

    raise RuntimeError('；'.join(errors))


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ProxyHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求 - 提供 HTML 文件、静态资源和官方基准"""
        parsed = urlparse(self.path)
        path   = parsed.path
        query  = parse_qs(parsed.query)

        if path == '/health':
            self.send_json_response(200, {
                'status': 'ok',
                'app': 'hlwy-ai-checker',
                'version': APP_VERSION,
            })
        elif path == '/' or path == '/index.html':
            self.serve_html()
        elif path == '/chart.js':
            self.serve_static('chart.js', 'application/javascript')
        elif path == '/api/baselines':
            self.serve_baseline_list(query)
        elif path == '/api/baseline':
            self.serve_baseline_file(query)
        elif path == '/api/capability/status':
            self.send_json_response(200, _capability_engine_status())
        elif path == '/api/capability/job':
            self.serve_capability_job(query)
        else:
            self.send_error(404, "File not found")

    def serve_baseline_list(self, query):
        """返回 GitHub baselines 目录下的模型列表"""
        force = query.get('refresh', ['0'])[0] in ('1', 'true')
        try:
            models, source = fetch_baseline_list(force=force)
            self.send_json_response(200, {
                'models': models,
                'count': len(models),
                'source': source,
                'repo': f'{GITHUB_OWNER}/{GITHUB_REPO}',
            })
        except Exception as e:
            self.send_json_response(502, {
                'error': '无法获取官方基准列表',
                'detail': str(e),
            })

    def serve_baseline_file(self, query):
        """下载并返回单个官方基准"""
        name = (query.get('name', [''])[0] or '').strip()
        if not name:
            self.send_json_response(400, {'error': '缺少 name 参数'})
            return
        if not _SAFE_NAME_RE.match(name):
            self.send_json_response(400, {'error': '基准名称不合法'})
            return

        force = query.get('refresh', ['0'])[0] in ('1', 'true')
        try:
            data, source = fetch_baseline_file(name, force=force)
            self.send_json_response(200, {'name': name, 'source': source, 'data': data})
        except Exception as e:
            self.send_json_response(502, {
                'error': f'无法下载基准「{name}」',
                'detail': str(e),
            })

    def do_POST(self):
        """处理 POST 请求 - 代理 API 调用"""
        if urlparse(self.path).path == '/api/capability/run':
            self.start_capability_job()
            return
        if urlparse(self.path).path == '/api/capability/stop':
            self.stop_capability_job()
            return
        # 代理所有 OpenAI 和 Anthropic API 请求
        if '/chat/completions' in self.path or '/messages' in self.path or '/responses' in self.path:
            self.proxy_api_request()
        else:
            self.send_error(404, "Endpoint not found")

    def start_capability_job(self):
        """Queue one local EvalScope job; the API key never enters job state or a CLI argument."""
        if not _capability_engine_status()['installed']:
            self.send_json_response(503, {
                'error': 'EvalScope 尚未安装',
                'install_script': 'scripts/Install-Capability-Engine.ps1',
            })
            return
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0 or content_length > 128 * 1024:
                raise ValueError('请求体大小不合法')
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
            config, api_key = _validate_capability_config(payload)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json_response(400, {'error': str(exc)})
            return

        job_id = uuid.uuid4().hex
        with _capability_jobs_lock:
            _capability_jobs[job_id] = {
                'status': 'queued',
                'created_at': time.time(),
                'output': '',
                'config': {key: value for key, value in config.items() if key != 'api_key'},
            }
        threading.Thread(
            target=_run_capability_job,
            args=(job_id, config, api_key),
            name=f'evalscope-{job_id[:8]}',
            daemon=True,
        ).start()
        self.send_json_response(202, {'job_id': job_id, 'status': 'queued'})

    def serve_capability_job(self, query):
        job_id = (query.get('id', [''])[0] or '').strip()
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            self.send_json_response(400, {'error': '任务 ID 不合法'})
            return
        with _capability_jobs_lock:
            job = _capability_jobs.get(job_id)
            if not job:
                self.send_json_response(404, {'error': '任务不存在或已清理'})
                return
            response = dict(job)
        self.send_json_response(200, response)

    def stop_capability_job(self):
        """Stop a running optional evaluation process."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(content_length).decode('utf-8')) if content_length else {}
            job_id = str(payload.get('job_id', '')).strip()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json_response(400, {'error': str(exc)})
            return
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            self.send_json_response(400, {'error': '任务 ID 不合法'})
            return
        with _capability_jobs_lock:
            job = _capability_jobs.get(job_id)
            process = _capability_processes.get(job_id)
            if not job:
                self.send_json_response(404, {'error': '任务不存在或已清理'})
                return
            if job.get('status') not in ('queued', 'running'):
                self.send_json_response(200, {'status': job.get('status'), 'job_id': job_id})
                return
            job['status'] = 'stopping'
        if process and process.poll() is None:
            process.terminate()
        self.send_json_response(202, {'status': 'stopping', 'job_id': job_id})

    def serve_html(self):
        """返回 HTML 文件"""
        try:
            with open(os.path.join(BASE_DIR, 'hlwy-ai-checker.html'), 'r', encoding='utf-8') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "hlwy-ai-checker.html not found")

    def serve_static(self, filename, content_type):
        """返回静态文件"""
        try:
            with open(os.path.join(BASE_DIR, filename), 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, f"{filename} not found")

    def proxy_api_request(self):
        """代理 API 请求到真实的 API 端点"""
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # 确定目标 URL
            if '/chat/completions' in self.path:
                # OpenAI Chat Completions API
                base_url = _normalize_openai_base_url(
                    self.headers.get('X-Target-Base-URL', 'https://api.openai.com/v1')
                )
                target_url = f"{base_url.rstrip('/')}/chat/completions"
            elif '/responses' in self.path:
                # OpenAI Responses API
                base_url = _normalize_openai_base_url(
                    self.headers.get('X-Target-Base-URL', 'https://api.openai.com/v1')
                )
                target_url = f"{base_url.rstrip('/')}/responses"
            elif '/messages' in self.path:
                # Anthropic API
                base_url = self.headers.get('X-Target-Base-URL', 'https://api.anthropic.com/v1')
                target_url = f"{base_url.rstrip('/')}/messages"
            else:
                self.send_json_response(400, {'error': '不支持的 API 端点'})
                return

            # 获取请求头伪装预设
            header_preset = self.headers.get('X-Header-Preset', 'default')

            # 构建代理请求头 (全小写 key)
            if header_preset in HEADER_PRESETS:
                headers = dict(HEADER_PRESETS[header_preset])
                # 每次请求动态生成唯一 request-id
                headers['x-request-id'] = f'req_{uuid.uuid4().hex}'
            else:
                headers = dict(DEFAULT_BROWSER_HEADERS)

            # 复制必要的业务请求头 (保持小写 key)
            header_map = {
                'Content-Type': 'content-type',
                'Authorization': 'authorization',
                'anthropic-version': 'anthropic-version',
                'x-api-key': 'x-api-key',
            }
            for src_key, dst_key in header_map.items():
                val = self.headers.get(src_key)
                if val:
                    headers[dst_key] = val

            # 移除 accept-encoding 避免收到压缩响应后原样转发导致浏览器解析失败
            headers.pop('accept-encoding', None)

            # 使用 requests 发送请求 (保留原始 header 大小写)
            try:
                resp = _session.post(
                    target_url,
                    data=body,
                    headers=headers,
                    timeout=30,
                )

                self.send_response(resp.status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(resp.content)

            except req_lib.exceptions.ConnectionError as e:
                self.send_json_response(500, {'error': f'网络错误: {str(e)}'})
            except req_lib.exceptions.Timeout as e:
                self.send_json_response(504, {'error': f'请求超时: {str(e)}'})

        except Exception as e:
            self.send_json_response(500, {'error': f'服务器错误: {str(e)}'})

    def send_json_response(self, status_code, data):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_cors_headers(self):
        """仅允许本机工具页面跨域，避免任意网页调用本地 API 代理。"""
        origin = self.headers.get('Origin')
        port = self.server.server_address[1]
        allowed_origins = {
            f'http://127.0.0.1:{port}',
            f'http://localhost:{port}',
        }
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, anthropic-version, x-api-key, X-Target-Base-URL, X-Header-Preset')

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    host = '127.0.0.1'
    try:
        port = int(os.environ.get('HLWY_PORT', '8000'))
    except ValueError:
        print("错误: HLWY_PORT 必须是整数")
        return 2
    if not (1 <= port <= 65535):
        print("错误: 端口必须在 1-65535 之间")
        return 2

    html_path = os.path.join(BASE_DIR, 'hlwy-ai-checker.html')
    if not os.path.exists(html_path):
        print(f"错误: 找不到 {html_path}")
        return 2

    try:
        server = ThreadingHTTPServer((host, port), ProxyHandler)
    except OSError as exc:
        print(f"错误: 无法监听 {host}:{port}: {exc}")
        return 2

    url = f'http://{host}:{port}'
    print(f"""
╔════════════════════════════════════════════════════════╗
║   hlwy-ai-checker {APP_VERSION} - AI 模型防掺水检测     ║
╚════════════════════════════════════════════════════════╝
上游项目：https://github.com/hanlinwenyuan/hlwy-ai-checker

🌐 本地访问地址: {url}
🔒 仅监听 127.0.0.1；API Key 只在本次浏览器页面和请求内使用
⚡ 「一键鉴别」会在线下载官方统计基准，无需手动标定

按 Ctrl+C 停止
""")

    no_browser = os.environ.get('HLWY_NO_BROWSER', '').lower() in {'1', 'true', 'yes'}
    if not no_browser:
        threading.Timer(0.5, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n已停止")
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
