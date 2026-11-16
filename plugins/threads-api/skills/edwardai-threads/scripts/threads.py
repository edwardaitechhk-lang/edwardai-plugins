#!/usr/bin/env python3
"""Threads single-text publisher. Credentials stay local; receipts prevent retries."""
import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://graph.threads.net/v1.0/'
DEFAULT = Path.home() / '.config/edwardai-threads/account.json'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as f:
        os.chmod(f.name, 0o600)
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, path)
    assert json.loads(path.read_text()) == value


def request(config, endpoint, params=None, method='GET'):
    if not re.fullmatch(r'[A-Za-z0-9_/]+', endpoint):
        raise ValueError('Invalid endpoint')
    encoded = urllib.parse.urlencode(params or {}).encode()
    url = API + endpoint
    data = None
    if method == 'GET' and encoded:
        url += '?' + encoded.decode()
    elif method == 'POST':
        data = encoded
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + config['access_token'],
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            details = json.loads(e.read()).get('error', {})
        except Exception:
            details = {}
        raise RuntimeError(f"API HTTP {e.code}, code={details.get('code')}, subcode={details.get('error_subcode')}; credential suppressed") from None
    except Exception:
        raise RuntimeError('API response unavailable; do not retry a write without reconciliation') from None


def identity(config):
    result = request(config, 'me', {'fields': 'id,username'})
    if result.get('username') != config['expected_username']:
        raise RuntimeError('Account mismatch; stopped before publishing')
    return result


def content(path):
    value = Path(path).read_text(encoding='utf-8').strip()
    if not value or len(value) > 500:
        raise ValueError('Single text post must contain 1-500 characters; review current platform limits for longer content')
    return value, hashlib.sha256(value.encode()).hexdigest()


def verify(config, post_id, expected=None):
    result = request(config, str(post_id), {'fields': 'id,text,username,permalink,timestamp'})
    if result.get('username') != config['expected_username']:
        raise RuntimeError('Published account mismatch')
    if expected is not None and result.get('text') != expected:
        raise RuntimeError('Published text mismatch; inspect existing post, do not resend')
    if not result.get('permalink'):
        raise RuntimeError('Permalink missing; verification incomplete')
    return result


def publish(config, config_path, text, digest, approved):
    if digest != approved:
        raise ValueError('Approval hash does not match final text')
    who = identity(config)
    directory = config_path.parent / 'receipts' / who['username']
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (digest + '.json')
    if path.exists():
        state = json.loads(path.read_text())
        if state.get('post_id'):
            state['readback'] = verify(config, state['post_id'], text)
            state['phase'] = 'verified'
            save(path, state)
            return state
        raise RuntimeError('Existing attempt is locked. Read receipt and reconcile; no automatic resend.')
    state = {'username': who['username'], 'text': text, 'sha256': digest,
             'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'phase': 'create_attempted'}
    # O_EXCL coordinates concurrent invocations. A crash leaves a blocking intent.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    try:
        created = request(config, who['id'] + '/threads', {'media_type': 'TEXT', 'text': text}, 'POST')
        state['container_id'] = created['id']
        state['phase'] = 'container_created'
        save(path, state)
        ready = None
        for n in range(12):
            ready = request(config, state['container_id'], {'fields': 'status,error_message'})
            if ready.get('status') != 'IN_PROGRESS':
                break
            if n < 11:
                time.sleep(2)
        if ready.get('status') != 'FINISHED':
            state['container_status'] = ready.get('status')
            save(path, state)
            raise RuntimeError('Container is not FINISHED; receipt retained, no automatic recreation')
        state['phase'] = 'publish_attempted'
        save(path, state)
        result = request(config, who['id'] + '/threads_publish', {'creation_id': state['container_id']}, 'POST')
        state['post_id'] = result['id']
        state['phase'] = 'published_unverified'
        save(path, state)
        state['readback'] = verify(config, state['post_id'], text)
        state['phase'] = 'verified'
        save(path, state)
        return state
    except Exception:
        # Preserve the last known phase; never serialize exceptions/credentials.
        state['needs_reconciliation'] = True
        save(path, state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('me')
    sub.add_parser('preview').add_argument('file')
    post = sub.add_parser('publish'); post.add_argument('file'); post.add_argument('--approve-hash', required=True)
    for command, field in [('verify', 'post_id'), ('status', 'container_id'), ('receipt', 'hash')]:
        sub.add_parser(command).add_argument(field)
    listing = sub.add_parser('list'); listing.add_argument('--pages', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'init':
        if args.config.exists():
            raise ValueError('Private config exists; inspect it locally rather than overwriting')
        username = input('Your Threads username (without @): ').strip().lstrip('@')
        token = getpass.getpass('Access token (hidden input): ').strip()
        if not re.fullmatch(r'[A-Za-z0-9._]+', username) or not token:
            raise ValueError('Username or token missing')
        config = {'expected_username': username, 'access_token': token}
        result = identity(config)
        save(args.config, config)
    elif args.command == 'preview':
        text, digest = content(args.file)
        username = json.loads(args.config.read_text()).get('expected_username') if args.config.exists() else '(not connected)'
        result = {'username': username, 'text': text, 'sha256': digest, 'characters': len(text), 'network_writes': 0}
    else:
        if os.name != 'nt' and args.config.stat().st_mode & 0o077:
            raise ValueError('Credential file must be private (chmod 600)')
        config = json.loads(args.config.read_text())
        if args.command == 'me':
            result = identity(config)
        elif args.command == 'publish':
            text, digest = content(args.file)
            result = publish(config, args.config, text, digest, args.approve_hash)
        elif args.command == 'verify':
            result = verify(config, args.post_id)
        elif args.command == 'status':
            result = request(config, args.container_id, {'fields': 'status,error_message'})
        elif args.command == 'receipt':
            if not re.fullmatch(r'[a-f0-9]{64}', args.hash):
                raise ValueError('Invalid content hash')
            username = config['expected_username']
            if not re.fullmatch(r'[A-Za-z0-9._]+', username):
                raise ValueError('Invalid username')
            result = json.loads((args.config.parent / 'receipts' / username / (args.hash + '.json')).read_text())
        elif args.command == 'list':
            if not 1 <= args.pages <= 20:
                raise ValueError('Read 1-20 pages per bounded request')
            identity(config)
            rows, after, has_more = [], None, False
            for page in range(args.pages):
                params = {'fields': 'id,text,permalink,timestamp', 'limit': 50}
                if after: params['after'] = after
                response = request(config, 'me/threads', params)
                rows.extend(response.get('data', []))
                paging = response.get('paging', {})
                after = paging.get('cursors', {}).get('after')
                has_more = bool(paging.get('next') and after)
                if not has_more: break
            result = {'data': rows, 'pages_read': page + 1, 'has_more': has_more}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as e:
        # Our own errors never interpolate request headers or tokens.
        print(str(e) if isinstance(e, (RuntimeError, ValueError)) else 'Operation stopped; inspect private receipt before any retry')
        raise SystemExit(1)
