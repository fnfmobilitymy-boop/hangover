"""Deploy a specific commit to an existing Render service; never print credentials."""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def configuration():
    key = os.environ.get('RENDER_API_KEY', '')
    service = os.environ.get('RENDER_SERVICE_ID', '')
    if not key or not re.fullmatch(r'srv-[A-Za-z0-9]+', service):
        raise RuntimeError('Set GitHub secret RENDER_API_KEY and repository variable RENDER_SERVICE_ID. See backend/DEPLOYMENT.md.')
    return key, service


def request_json(url, key=None, body=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'KENNY-GitHub-Actions'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Provider response bodies may contain configuration; do not log them.
        raise RuntimeError(f'Deployment request failed (HTTP {error.code}). Check Render access and service settings.') from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError('Deployment endpoint unavailable or returned invalid JSON.') from None


def public_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise RuntimeError('Render did not return a valid public HTTPS service URL.')
    return value.rstrip('/')


def deploy():
    key, service = configuration()
    if '--check' in sys.argv:
        print('Deployment settings are present.')
        return
    commit = os.environ.get('KENNY_DEPLOY_COMMIT', '')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise RuntimeError('KENNY_DEPLOY_COMMIT must be the full tested Git commit SHA.')
    base = 'https://api.render.com/v1/services/' + service
    info = request_json(base, key)
    url = public_origin(info.get('serviceDetails', {}).get('url', ''))
    if info.get('type') != 'web_service' or info.get('branch') != 'main':
        raise RuntimeError('Expected a Render web service tracking the main branch.')
    result = request_json(base + '/deploys', key, {'clearCache': 'do_not_clear', 'commitId': commit})
    deploy_id = result.get('id', '')
    if not re.fullmatch(r'dep-[A-Za-z0-9]+', deploy_id):
        raise RuntimeError('Render did not return a deployment ID.')
    print('Deployment requested. Waiting for Render…', flush=True)
    deadline = time.monotonic() + 18 * 60
    while time.monotonic() < deadline:
        current = request_json(base + '/deploys/' + deploy_id, key)
        status = current.get('status')
        if status == 'live':
            if current.get('commit', {}).get('id') != commit:
                raise RuntimeError('Live deployment commit differs from the tested commit.')
            break
        if status in ('build_failed', 'update_failed', 'pre_deploy_failed', 'canceled', 'deactivated'):
            raise RuntimeError('Render deployment ended with status: ' + status)
        time.sleep(10)
    else:
        raise RuntimeError('Deployment timed out. Check Render before retrying; it may still be running.')
    for attempt in range(12):
        try:
            health = request_json(url + '/api/health')
            if health.get('service') != 'kenny-api' or health.get('status') != 'ok':
                raise RuntimeError('Public API did not report healthy KENNY backend.')
            break
        except RuntimeError:
            if attempt == 11:
                raise
            time.sleep(5)
    with urllib.request.urlopen(url + '/admin/', timeout=30) as response:
        if response.status != 200 or b'admin/app.js' not in response.read():
            raise RuntimeError('Admin page verification failed.')
    print('Verified storefront: ' + url + '/')
    print('Verified admin: ' + url + '/admin/')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as handle:
            handle.write(f'## KENNY deployment verified\n\nStorefront: {url}/\n\nAdmin: {url}/admin/\n\nCommit: `{commit}`\n')


if __name__ == '__main__':
    try:
        deploy()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
