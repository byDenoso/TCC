"""Install the operator-authorized operational rollout through the existing Writer.

The Git file is first-install code configuration only. After admission, Drive
owns the frozen definition. Changes never overwrite the installed configuration.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import subprocess
from .operational_control import digest, require, validate_definition, WORKFLOW

CONFIG_ENTITY = 'entities/artifact/OPERATIONAL-CONTROL-RUNTIME-V1.json'
ROLLOUT_PATH = 'nexo-control/operational-runtime.json'
WRITER_REF = 'byDenoso/Pantheon/.github/workflows/nexo-writer-robot.yml@refs/heads/main'
REPOSITORY = 'byDenoso/Pantheon'
FOLDER_ID = '1yxu9dbbMlNv-Nc_jfZDcunTkMxTjcx9H'


def canonical_config(data):
    entry = data.get('files', {}).get(CONFIG_ENTITY, {}).get('value', {})
    if entry:
        require(entry.get('kind') == 'NEXO_OPERATIONAL_RUNTIME_V1', 'CONFIG_IDENTITY_CONFLICT')
        return copy.deepcopy(entry.get('payload'))
    return copy.deepcopy(data.get('files', {}).get('contracts/OPERATIONAL_RUNTIME_V1.json', {}).get('value'))


def freeze_rollout(template, checkout, env):
    """Resolve hashes from the reviewed main checkout, not from agent arguments."""
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_WORKFLOW_REF') == WRITER_REF and
            env.get('GITHUB_REPOSITORY') == REPOSITORY and env.get('GITHUB_REF') == 'refs/heads/main',
            'EXISTING_SINGLETON_WRITER_REQUIRED')
    commit = env.get('GITHUB_SHA', '')
    require(re.fullmatch('[a-f0-9]{40}', commit), 'ROLLOUT_COMMIT_REQUIRED')
    observed = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    require(observed == commit, 'ROLLOUT_CHECKOUT_MISMATCH')
    require(template.get('contract') == 'NEXO_OPERATIONAL_RUNTIME_V1' and template.get('enabled') is True and
            template.get('publication_authorized') is True and template.get('approval_ref'), 'ROLLOUT_NOT_AUTHORIZED')
    require(template.get('allowed_folder_ids') == [FOLDER_ID], 'ROLLOUT_DESTINATIONS_CHANGED')
    work = template.get('work', [])
    require(len(work) == 1 and work[0].get('id') == 'OPERATIONAL-CONTROL-DRIVE-SUM-V1', 'ROLLOUT_SCOPE_INVALID')
    config = copy.deepcopy(template)
    code = {'repository': REPOSITORY, 'sha': commit, 'files': {}}
    for name in (WORKFLOW, 'scripts/nexo_operational_package.py'):
        path = checkout / name
        require(path.is_file() and not path.is_symlink(), 'ROLLOUT_SOURCE_MISSING')
        code['files'][name] = digest(path.read_bytes())
    for definition in config['work']:
        require(set(definition['destinations'].values()) == {FOLDER_ID}, 'ROLLOUT_DESTINATIONS_CHANGED')
        definition['code'] = code
        validate_definition(definition)
    config['installed_from'] = {'repository': REPOSITORY, 'commit': commit, 'path': ROLLOUT_PATH,
                                'template_sha256': digest(template)}
    return config


def install_if_requested(store, data, env):
    config = canonical_config(data)
    if config is not None:
        return config
    checkout = Path(env.get('GITHUB_WORKSPACE') or '.')
    path = checkout / ROLLOUT_PATH
    if not path.is_file():
        return None
    require(not path.is_symlink() and path.stat().st_size <= 32768, 'ROLLOUT_FILE_INVALID')
    template = json.loads(path.read_bytes())
    return store.install_config(freeze_rollout(template, checkout, env))
