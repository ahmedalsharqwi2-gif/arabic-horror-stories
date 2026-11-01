"""Prepare a reviewable, single-commit workflow switch after full acceptance.

This never pushes or cancels jobs. The operator must drain old runs before merging
its exact changes. Original workflow bytes are retained outside workflows/.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .gate import evaluate, PROFILES


def prepare(manifest, repository, profile, replacement, *, legacy_drained=False):
    import yaml
    root = Path(repository).resolve()
    if profile not in PROFILES:
        raise ValueError('Unknown acceptance profile')
    # Re-evaluate real films, narration, history and renderer hashes now. A saved
    # boolean from an older test run cannot authorize a workflow switch.
    report = evaluate(manifest)
    if not report['cutover_eligible']:
        raise ValueError('All five complete films must pass current acceptance')
    if not legacy_drained:
        raise ValueError('Legacy in-flight runs must be drained before cutover')
    candidate = yaml.safe_load(Path(replacement).read_text())
    if not isinstance(candidate, dict) or not candidate.get('jobs'):
        raise ValueError('A concrete production workflow is required')
    if candidate.get('concurrency', {}).get('cancel-in-progress') is not False:
        raise ValueError('Production must serialize and retain in-flight work')
    expected = 'professional-daily-' + profile
    if candidate.get('concurrency', {}).get('group') != expected:
        raise ValueError('Replacement must share the existing production concurrency group')
    if 'production_v2.daily' not in Path(replacement).read_text():
        raise ValueError('Replacement must execute the guarded production v2 entrypoint')
    config_path = root / 'config/production_v2.json'
    config = json.loads(config_path.read_text())
    if config.get('profile') != profile or config.get('active_pipeline') != 'legacy':
        raise ValueError('Expected the matching retained legacy configuration')
    changes = []
    # Read and validate everything before writing. Keep audit/test workflows;
    # every old professional production/recovery launcher loses execution paths.
    for path in sorted((root / '.github/workflows').glob('professional-*.y*ml')):
        raw = path.read_bytes()
        workflow = yaml.safe_load(raw)
        if not isinstance(workflow, dict) or not isinstance(workflow.get('jobs'), dict):
            raise ValueError('Cannot safely inspect a legacy launcher')
        for job in workflow['jobs'].values():
            job['if'] = '${{ false }}'
        workflow['on'] = {'workflow_dispatch': {}}
        workflow.pop(True, None)
        archive = root / '.github/legacy-before-production-v2' / (path.name + '.txt')
        if archive.exists():
            raise FileExistsError('An earlier switch archive is retained')
        changes.append((path, archive, raw, yaml.safe_dump(workflow, sort_keys=False, allow_unicode=True)))
    if not any(row[0].name == 'professional-daily.yml' for row in changes):
        raise ValueError('The known legacy daily launcher was not found')
    target = root / '.github/workflows/production-v2-daily.yml'
    if target.exists():
        raise FileExistsError('A replacement daily workflow already exists')
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    config.update(active_pipeline='production_v2', automatic_cutover=False,
                  acceptance_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
                  reason='Five full films accepted; legacy launchers disabled in the same commit')
    for path, archive, raw, updated in changes:
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(raw)
        path.write_text(updated)
    target.write_bytes(Path(replacement).read_bytes())
    (root / 'config/production_v2_acceptance.json').write_bytes(report_bytes)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    return {'profile': profile, 'prepared': True, 'pushed': False,
            'legacy_launchers_disabled': [row[0].name for row in changes],
            'requires_one_commit': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--root', default='.', type=Path)
    parser.add_argument('--profile', required=True, choices=PROFILES)
    parser.add_argument('--replacement', required=True, type=Path)
    parser.add_argument('--legacy-drained', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(json.loads(args.manifest.read_text()), args.root,
          args.profile, args.replacement, legacy_drained=args.legacy_drained), indent=2))


if __name__ == '__main__':
    main()
