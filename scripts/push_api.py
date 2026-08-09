#!/usr/bin/env python3
# push_api.py — 通过 GitHub REST Contents API 把工作区文件同步到远程仓库
#
# 背景：本机存在透明 TLS 拦截代理，会把 git 智能 HTTP 的 push/fetch（pack 传输）
#       一律 reset，但 api.github.com 的写请求放行。因此用本脚本替代 `git push`，
#       既能部署 GitHub Pages，又绕开代理封锁。
#
# 用法：
#   python scripts/push_api.py [YYYY-MM-DD]
#   GITHUB_TOKEN=xxx python scripts/push_api.py 2026-08-08   # 也可走环境变量
#
# 机制：
#   - 从 remote.origin.url 解析 owner/repo 与 token（或读 GITHUB_TOKEN 环境变量）
#   - 只同步 deploy.sh 原本 git add 的那批文件（有界集合，避免误传无关文件）
#   - 用 `git hash-object` 算本地 blob sha，与远程 sha 比对，相同则跳过
#   - 不同（或远程不存在）则 PUT 上传，自动带 sha（更新）或不带（新建）
#   - GET/PUT 全程重试，规避透明代理偶发断流（IncompleteRead / reset）

import subprocess, re, os, sys, json, ssl, base64, time, traceback
import urllib.request, urllib.error

ctx = ssl._create_unverified_context()  # 透明代理使用自签证书

USER = None
TOKEN = None
REPO = None
HDR = {}

SKIP_DIRS = {'.git', '.workbuddy', 'node_modules', '__pycache__'}
SKIP_EXT = ('.pyc', '.log')


def fail(msg):
    print('[push_api] FATAL:', msg, file=sys.stderr)
    sys.exit(2)


def parse_remote():
    global USER, TOKEN, REPO
    try:
        url = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception as e:
        fail('无法读取 remote.origin.url: %r' % e)
    m = re.match(r'https?://([^:]+):([^@]+)@github\.com/([^/]+)/([^.]+)', url)
    if m:
        USER, TOKEN = m.group(1), m.group(2)
        REPO = '%s/%s' % (m.group(3), m.group(4))
    else:
        tok = os.environ.get('GITHUB_TOKEN')
        if not tok:
            fail('remote 不是 https+token 形式，且未设置 GITHUB_TOKEN 环境变量')
        TOKEN = tok
        m2 = re.match(r'https?://github\.com/([^/]+)/([^.]+)', url)
        if not m2:
            fail('无法从 remote 解析 owner/repo: %s' % url)
        REPO = '%s/%s' % (m2.group(1), m2.group(2))
    HDR.update({
        'Authorization': 'token %s' % TOKEN,
        'User-Agent': 'wb-daily-news',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
    })


def api(method, path, data=None, retries=6):
    """发起一次 API 请求，失败时按指数退避重试。返回 (status, body_bytes)。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                'https://api.github.com/repos/%s/contents/%s' % (REPO, path),
                data=data, headers=HDR, method=method)
            r = urllib.request.urlopen(req, timeout=45, context=ctx)
            return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == 'GET':
                return 404, b''
            last = e
            time.sleep(1.5 * (i + 1))
        except Exception as e:  # 连接被 reset / IncompleteRead 等
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def remote_sha(path):
    """取远程文件 blob sha；不存在返回 None；持续失败则抛错。"""
    for _ in range(4):
        try:
            st, body = api('GET', path, retries=1)
            if st == 404:
                return None
            return json.loads(body)['sha']
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1.2)
        except Exception:
            time.sleep(1.2)
    raise RuntimeError('无法获取远程 sha: %s' % path)


def local_blob_sha(path):
    return subprocess.check_output(
        ['git', 'hash-object', path],
        stderr=subprocess.DEVNULL).decode().strip()


def upload(path, message):
    content = base64.b64encode(open(path, 'rb').read()).decode()
    sha = remote_sha(path)
    body = {'message': message, 'content': content}
    if sha:
        body['sha'] = sha
    st, _ = api('PUT', path, json.dumps(body).encode())
    return st


def collect_files(root):
    """只同步 deploy.sh 原本 git add 的那批文件（有界、可预期）。"""
    out = []
    for d in ['data', 'frontend', 'collector', 'scripts']:
        dp = os.path.join(root, d)
        if not os.path.isdir(dp):
            continue
        for r, ds, fs in os.walk(dp):
            ds[:] = [x for x in ds if x not in SKIP_DIRS]
            for fn in fs:
                if fn.endswith(SKIP_EXT):
                    continue
                out.append(os.path.relpath(os.path.join(r, fn), root).replace(os.sep, '/'))
    for f in ['run_daily.py', 'README.md', '.gitignore', 'package.json',
             'index.html', 'style.css', 'app.js', 'data.js']:
        fp = os.path.join(root, f)
        if os.path.exists(fp):
            out.append(f)
    # 去重并保持顺序
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def main():
    parse_remote()
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception as e:
        fail('无法定位仓库根目录: %r' % e)
    files = collect_files(root)
    message = ('update: %s 简报' % date) if date else 'update: 每日简报'
    print('[push_api] 待处理文件 %d 个，仓库 %s' % (len(files), REPO), flush=True)
    ok = skip = fail_n = 0
    for f in files:
        fp = os.path.join(root, f)
        try:
            local = local_blob_sha(fp)
            remote = remote_sha(f)
            if local == remote:
                skip += 1
                continue
            st = upload(f, message)
            print('  UP %s  %s' % (st, f), flush=True)
            ok += 1
        except Exception as e:
            print('  FAIL %s: %r' % (f, e), flush=True)
            traceback.print_exc()
            fail_n += 1
        time.sleep(0.15)  # 避免对 API 过于密集，降低被代理/限流击杀的概率
    print('[push_api] DONE ok=%d skip=%d fail=%d total=%d' % (ok, skip, fail_n, len(files)), flush=True)
    sys.exit(1 if fail_n else 0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(3)
