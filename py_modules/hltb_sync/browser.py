"""Bound Steam CEF target: same-origin HTTP, never cookie extraction.

Steam already exposes the loopback CEF endpoint used by Decky. Only a newly
opened/marked HLTB target can be connected. No remote debugger URLs are trusted.
"""
import asyncio
import base64
import hashlib
import json
import secrets
import socket
import struct
import time
import http.client
from urllib.parse import urlsplit

ORIGIN = 'https://howlongtobeat.com'
MAX_BYTES = 12 * 1024 * 1024


class IntegrationError(Exception):
    """Public, fixed error code; never include response contents."""


def is_hltb(url):
    parsed = urlsplit(url)
    return parsed.scheme == 'https' and parsed.netloc == 'howlongtobeat.com'


class CEF:
    def targets(self):
        connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=5)
        try:
            # Direct loopback HTTP avoids environment proxies and urllib.request,
            # which is not guaranteed to exist in Decky's frozen Python runtime.
            connection.request('GET', '/json/list')
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError()
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError()
            targets = json.loads(data)
            if not isinstance(targets, list):
                raise ValueError()
            return targets
        except Exception:
            raise IntegrationError('browser_unavailable') from None
        finally:
            connection.close()

    def evaluate(self, target, expression):
        url = urlsplit(target['webSocketDebuggerUrl'])
        if url.scheme != 'ws' or url.hostname not in ('localhost', '127.0.0.1') or url.port != 8080:
            raise IntegrationError('unsafe_browser_endpoint')
        try:
            with socket.create_connection(('127.0.0.1', 8080), timeout=5) as sock:
                deadline = time.monotonic() + 25
                sock.settimeout(25)
                key = base64.b64encode(secrets.token_bytes(16)).decode()
                path = url.path + (('?' + url.query) if url.query else '')
                if any(c in path for c in '\r\n'):
                    raise ValueError()
                sock.sendall((f'GET {path} HTTP/1.1\r\nHost: localhost:8080\r\n'
                              'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                              f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())

                def read(n):
                    chunks = bytearray()
                    while len(chunks) < n:
                        sock.settimeout(max(0.01, deadline - time.monotonic()))
                        chunk = sock.recv(n - len(chunks))
                        if not chunk or time.monotonic() > deadline:
                            raise TimeoutError()
                        chunks.extend(chunk)
                    return bytes(chunks)

                header = b''
                while not header.endswith(b'\r\n\r\n'):
                    header += read(1)
                    if len(header) > 16384:
                        raise ValueError()
                expected = base64.b64encode(hashlib.sha1(
                    (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                headers = dict(line.split(':', 1) for line in header.decode().split('\r\n')[1:] if ':' in line)
                if b' 101 ' not in header.split(b'\r\n')[0] or not any(
                        k.lower() == 'sec-websocket-accept' and v.strip() == expected for k, v in headers.items()):
                    raise ValueError()

                def send(payload, opcode=1):
                    mask = secrets.token_bytes(4)
                    n = len(payload)
                    prefix = bytes([128 | opcode, 128 | (n if n < 126 else 126 if n < 65536 else 127)])
                    if n >= 126:
                        prefix += struct.pack('!H' if n < 65536 else '!Q', n)
                    sock.sendall(prefix + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))

                send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
                    'expression': expression, 'awaitPromise': True, 'returnByValue': True,
                    'userGesture': False}}).encode())
                fragments = b''
                while time.monotonic() < deadline:
                    a, b = read(2)
                    n = b & 127
                    if n >= 126:
                        n = struct.unpack('!H' if n == 126 else '!Q', read(2 if n == 126 else 8))[0]
                    if n + len(fragments) > MAX_BYTES:
                        raise ValueError()
                    mask = read(4) if b & 128 else None
                    payload = read(n)
                    if mask:
                        payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
                    opcode = a & 15
                    if opcode == 9:
                        send(payload, 10)
                        continue
                    if opcode == 10:
                        continue
                    if opcode == 8:
                        raise ConnectionError()
                    fragments += payload
                    if not a & 128:
                        continue
                    message = json.loads(fragments)
                    fragments = b''
                    if message.get('id') != 1:
                        continue
                    result = message.get('result', {})
                    if 'error' in message or 'exceptionDetails' in result:
                        raise ValueError()
                    return result['result']['value']
                raise TimeoutError()
        except Exception:
            raise IntegrationError('browser_request_failed') from None


class BrowserSession:
    def __init__(self, cef=None):
        self.cef = cef or CEF()
        self.target_id = None
        self.nonce = None
        self.existing = set()
        self.expires = 0
        self.marked_only = False

    async def begin(self):
        targets = await asyncio.to_thread(self.cef.targets)
        self.existing = {t['id'] for t in targets}
        self.nonce = secrets.token_urlsafe(24)
        self.expires = time.monotonic() + 300
        self.target_id = None
        return ORIGIN + '/login#decky-hltb-sync=' + self.nonce

    def disconnect(self):
        self.target_id = self.nonce = None
        self.expires = 0

    async def target(self):
        targets = await asyncio.to_thread(self.cef.targets)
        if self.target_id:
            match = next((t for t in targets if t['id'] == self.target_id and is_hltb(t.get('url', ''))), None)
            if match:
                return match
            raise IntegrationError('browser_closed_or_navigated')
        if not self.nonce or time.monotonic() > self.expires:
            raise IntegrationError('connect_required')
        candidates = [t for t in targets if is_hltb(t.get('url', '')) and (
            '#decky-hltb-sync=' + self.nonce in t['url'] or
            (not self.marked_only and t['id'] not in self.existing))]
        if len(candidates) != 1:
            raise IntegrationError('login_window_not_found')
        self.target_id = candidates[0]['id']
        return candidates[0]

    async def request(self, path, payload=None, *, method='GET', headers=None, referrer=None):
        if not path.startswith('/') or path.startswith('//') or '\\' in path:
            raise IntegrationError('invalid_hltb_path')
        target = await self.target()
        options = {'method': method, 'credentials': 'same-origin', 'cache': 'no-store',
                   'redirect': 'error', 'headers': {'Accept': 'application/json', **(headers or {})}}
        if referrer:
            options['referrer'] = ORIGIN + referrer
        if payload is not None:
            options['headers']['Content-Type'] = 'application/json'
            options['body'] = json.dumps(payload, ensure_ascii=False)
        # The origin check also executes in the target, protecting navigation races.
        expression = '''(async () => {
          if (location.origin !== "https://howlongtobeat.com") return {error:"wrong_origin"};
          try {
            const response = await fetch(PATH, {...OPTIONS, signal:AbortSignal.timeout(18000)});
            const text = await response.text();
            if (text.length > 10000000) return {error:"response_too_large"};
            return {status:response.status, text};
          } catch { return {error:"network_or_session_error"}; }
        })()'''.replace('PATH', json.dumps(path)).replace('OPTIONS', json.dumps(options))
        result = await asyncio.to_thread(self.cef.evaluate, target, expression)
        if not isinstance(result, dict) or result.get('error'):
            raise IntegrationError('network_or_session_error')
        if result.get('status') in (401, 403):
            raise IntegrationError('login_required')
        if not 200 <= result.get('status', 0) < 300:
            raise IntegrationError('hltb_http_error')
        return result['text']
