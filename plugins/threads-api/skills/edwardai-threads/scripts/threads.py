#!/usr/bin/env python3
"""Threads text and reply-chain publisher. Private receipts prevent repeat writes."""
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


def text_digest(text, reply_to_id=None):
    if reply_to_id is not None:
        if not re.fullmatch(r'[0-9]+', str(reply_to_id)):
            raise ValueError('Reply target must be a numeric published post ID')
        text = json.dumps({'text': text, 'reply_to_id': str(reply_to_id)}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def verify(config, post_id, expected=None, reply_to_id=None):
    fields = 'id,text,username,permalink,timestamp'
    if reply_to_id is not None:
        fields += ',is_reply,replied_to,root_post'
    result = request(config, str(post_id), {'fields': fields})
    if result.get('username') != config['expected_username']:
        raise RuntimeError('Published account mismatch')
    if expected is not None and result.get('text') != expected:
        raise RuntimeError('Published text mismatch; inspect existing post, do not resend')
    if not result.get('permalink'):
        raise RuntimeError('Permalink missing; verification incomplete')
    if reply_to_id is not None:
        parent = result.get('replied_to')
        parent_id = parent.get('id') if isinstance(parent, dict) else parent
        if str(parent_id) != str(reply_to_id) or result.get('is_reply') is not True:
            raise RuntimeError('Reply relationship unverified; stop before creating another post')
    return result


def publish(config, config_path, text, digest, approved, reply_to_id=None):
    if not text or len(text) > 500 or digest != text_digest(text, reply_to_id):
        raise ValueError('Content or reply target does not match the content hash')
    if digest != approved:
        raise ValueError('Approval hash does not match final text')
    who = identity(config)
    if reply_to_id is not None:
        verify(config, str(reply_to_id))  # This tool only chains the user's own posts.
    directory = config_path.parent / 'receipts' / who['username']
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (digest + '.json')
    if path.exists():
        state = json.loads(path.read_text())
        if state.get('reply_to_id') != reply_to_id or state.get('text') != text:
            raise RuntimeError('Receipt target/content mismatch; inspect before continuing')
        if state.get('post_id'):
            state['readback'] = verify(config, state['post_id'], text, reply_to_id)
            state['phase'] = 'verified'
            save(path, state)
            return state
        raise RuntimeError('Existing attempt is locked. Read receipt and reconcile; no automatic resend.')
    state = {'username': who['username'], 'text': text, 'sha256': digest,
             'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'phase': 'create_attempted'}
    if reply_to_id is not None:
        state['reply_to_id'] = reply_to_id
    # O_EXCL coordinates concurrent invocations. A crash leaves a blocking intent.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    try:
        params = {'media_type': 'TEXT', 'text': text}
        if reply_to_id is not None:
            params['reply_to_id'] = str(reply_to_id)
        created = request(config, who['id'] + '/threads', params, 'POST')
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
        state['readback'] = verify(config, state['post_id'], text, reply_to_id)
        state['phase'] = 'verified'
        save(path, state)
        return state
    except Exception:
        # Preserve the last known phase; never serialize exceptions/credentials.
        state['needs_reconciliation'] = True
        save(path, state)
        raise


def thread_content(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    posts = value.get('posts') if isinstance(value, dict) else None
    if not isinstance(posts, list) or not 2 <= len(posts) <= 20:
        raise ValueError('Thread JSON must have 2-20 posts in a posts array')
    if any(not isinstance(p, str) or not p.strip() or p != p.strip() or len(p) > 500 for p in posts):
        raise ValueError('Each post must be a reviewed 1-500 character string without outer whitespace')
    canonical = json.dumps({'posts': posts}, ensure_ascii=False, sort_keys=True)
    return posts, hashlib.sha256(canonical.encode()).hexdigest()


def publish_thread(config, config_path, posts, digest, approved):
    canonical = json.dumps({'posts': posts}, ensure_ascii=False, sort_keys=True)
    if hashlib.sha256(canonical.encode()).hexdigest() != digest or digest != approved:
        raise ValueError('Thread approval hash does not match the complete ordered text')
    if not 2 <= len(posts) <= 20 or any(not isinstance(p, str) or not p.strip() or p != p.strip() or len(p) > 500 for p in posts):
        raise ValueError('Invalid thread text')
    who = identity(config)
    path = config_path.parent / 'receipts' / who['username'] / ('thread-' + digest + '.json')
    state = {'username': who['username'], 'sha256': digest, 'posts': [], 'phase': 'in_progress'}
    parent = None
    for index, text in enumerate(posts):
        part_digest = text_digest(text, parent)
        part = publish(config, config_path, text, part_digest, part_digest, parent)
        # publish() reads an existing successful receipt, and locks uncertain attempts.
        state['posts'].append(part)
        state['completed'] = index + 1
        save(path, state)
        parent = part['post_id']
    state['phase'] = 'verified'
    save(path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('me')
    for command in ('preview', 'preview-thread'):
        preview = sub.add_parser(command); preview.add_argument('file')
        if command == 'preview': preview.add_argument('--reply-to')
    for command in ('publish', 'publish-thread'):
        post = sub.add_parser(command); post.add_argument('file'); post.add_argument('--approve-hash', required=True)
        if command == 'publish': post.add_argument('--reply-to')
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
    elif args.command in ('preview', 'preview-thread'):
        username = json.loads(args.config.read_text()).get('expected_username') if args.config.exists() else '(not connected)'
        if args.command == 'preview-thread':
            posts, digest = thread_content(args.file)
            result = {'username': username, 'posts': posts, 'sha256': digest, 'characters': [len(p) for p in posts], 'reply_order': 'each post replies to its predecessor', 'network_writes': 0}
        else:
            text, _ = content(args.file)
            digest = text_digest(text, args.reply_to)
            result = {'username': username, 'text': text, 'reply_to_id': args.reply_to, 'sha256': digest, 'characters': len(text), 'network_writes': 0}
    else:
        if os.name != 'nt' and args.config.stat().st_mode & 0o077:
            raise ValueError('Credential file must be private (chmod 600)')
        config = json.loads(args.config.read_text())
        if args.command == 'me':
            result = identity(config)
        elif args.command == 'publish':
            text, _ = content(args.file)
            digest = text_digest(text, args.reply_to)
            result = publish(config, args.config, text, digest, args.approve_hash, args.reply_to)
        elif args.command == 'publish-thread':
            posts, digest = thread_content(args.file)
            result = publish_thread(config, args.config, posts, digest, args.approve_hash)
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
