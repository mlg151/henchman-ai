"""Publish the checked 0.4.0 files to production PyPI without exposing credentials."""
import configparser
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import tarfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

base = Path(__file__).resolve().parent
suite = ET.parse(base/'pytest-final.xml').getroot()
cases = list(suite.iter('testcase'))
assert len(cases) >= 8000, 'Full suite has not completed'
assert not any(case.find('failure') is not None or case.find('error') is not None for case in cases)
coverage = json.loads((base/'coverage-final.json').read_text())
assert coverage['totals']['percent_covered'] >= 90
manifest = json.loads((base/'manifest.json').read_text())
assert {entry['filename'] for entry in manifest} == {
    'henchman_ai-0.4.0-py3-none-any.whl', 'henchman_ai-0.4.0.tar.gz',
}
artifacts = []
for entry in manifest:
    path = base/'dist'/entry['filename']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    artifacts.append(str(path))
repository = base.parents[1]
with zipfile.ZipFile(base/'dist/henchman_ai-0.4.0-py3-none-any.whl') as archive:
    for name in archive.namelist():
        if name.startswith('henchman/') and not name.endswith('/'):
            assert archive.read(name) == (repository/'src'/name).read_bytes(), name
with tarfile.open(base/'dist/henchman_ai-0.4.0.tar.gz') as archive:
    for name in ('pyproject.toml','README.md','CHANGELOG.md'):
        member = archive.extractfile('henchman_ai-0.4.0/'+name)
        assert member is not None and member.read() == (repository/name).read_bytes(), name
config = configparser.ConfigParser(interpolation=None)
config.read(Path.home()/'.pypirc')
section = config['pypi']
assert urllib.parse.urlparse(section.get('repository','https://upload.pypi.org/legacy/')).hostname in {'upload.pypi.org','pypi.org'}
assert section.get('username','').strip() and section.get('password','').strip(), 'Production authentication is missing'
environment = {key:value for key,value in os.environ.items() if not key.startswith('UV_PUBLISH_')}
environment['UV_PUBLISH_USERNAME'] = section['username'].strip()
environment['UV_PUBLISH_PASSWORD'] = section['password'].strip()
result = subprocess.run([
    'uv','publish','--no-config','--trusted-publishing','never',
    '--publish-url','https://upload.pypi.org/legacy/',*artifacts,
],env=environment)
sys.exit(result.returncode)
