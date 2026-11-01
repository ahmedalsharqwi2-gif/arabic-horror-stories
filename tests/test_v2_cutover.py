import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
import yaml

from production_v2.cutover import prepare


def fixture(root):
    (root/'config').mkdir()
    (root/'.github/workflows').mkdir(parents=True)
    (root/'config/production_v2.json').write_text(json.dumps({'profile':'science','active_pipeline':'legacy'}))
    old=root/'.github/workflows/professional-daily.yml'
    old.write_text("name: Old daily\n'on':\n  schedule:\n  - cron: '5 18 * * *'\njobs:\n  produce:\n    runs-on: ubuntu-latest\n    steps:\n    - run: echo legacy\n")
    replacement=root/'replacement.yml'
    replacement.write_text("name: New daily\n'on':\n  workflow_dispatch: {}\nconcurrency:\n  group: professional-daily-science\n  cancel-in-progress: false\njobs:\n  produce:\n    runs-on: ubuntu-latest\n    steps:\n    - run: python -m production_v2.daily\n")
    return old,replacement


def test_failed_acceptance_never_modifies_workflows():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);old,replacement=fixture(root);before=old.read_bytes()
        with patch('production_v2.cutover.evaluate',return_value={'cutover_eligible':False}):
            with pytest.raises(ValueError,match='five complete'):prepare({},root,'science',replacement,legacy_drained=True)
        assert old.read_bytes()==before
        assert not (root/'.github/legacy-before-production-v2').exists()


def test_inflight_work_prevents_switch_even_with_accepted_films():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);old,replacement=fixture(root);before=old.read_bytes()
        with patch('production_v2.cutover.evaluate',return_value={'cutover_eligible':True}):
            with pytest.raises(ValueError,match='drained'):prepare({},root,'science',replacement)
        assert old.read_bytes()==before


def test_switch_disables_legacy_jobs_and_retains_exact_original_bytes():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);old,replacement=fixture(root);before=old.read_bytes()
        report={'cutover_eligible':True,'profiles':{}}
        with patch('production_v2.cutover.evaluate',return_value=report):
            result=prepare({},root,'science',replacement,legacy_drained=True)
        assert result['pushed'] is False
        updated=yaml.safe_load(old.read_text())
        assert 'schedule' not in updated['on']
        assert updated['jobs']['produce']['if']=='${{ false }}'
        assert (root/'.github/legacy-before-production-v2/professional-daily.yml.txt').read_bytes()==before
        assert (root/'.github/workflows/production-v2-daily.yml').read_bytes()==replacement.read_bytes()
        assert json.loads((root/'config/production_v2.json').read_text())['active_pipeline']=='production_v2'
