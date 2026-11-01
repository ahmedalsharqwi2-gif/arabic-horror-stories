from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from professional_motion import editorial
from professional_motion.horror_sources import candidates,validate_source,CAPTAIN_KEY,CAPTAIN_URL


def catalog():
    return json.loads(Path('professional_motion/catalog.json').read_text())['horror']


def test_directed_bank_does_not_spend_editorial_calls_on_unsupported_old_vessels():
    schema=deepcopy(editorial.SCHEMA);schema['properties']['visual_plan']={'type':'OBJECT'}
    with patch.object(editorial,'SCHEMA',schema),patch.object(editorial.requests,'get',side_effect=AssertionError('A feed is not an executable source bank')):
        rows=editorial.candidates('horror')
    assert [r['key'] for r in rows]==[CAPTAIN_KEY]
    assert rows[0]['director_contract']['world']=='stormship_inquiry'


def test_legacy_candidate_list_is_retained():
    with patch.object(editorial.requests,'get',side_effect=editorial.requests.RequestException('offline')):
        rows=editorial.candidates('horror')
    assert len(rows)>=5
    assert 'franklin-expedition-1845' in {r['key'] for r in rows}


def test_wrong_article_or_unknown_world_is_rejected():
    for url in ['https://www.rmg.co.uk/stories/maritime-history/mystery-mary-celeste',CAPTAIN_URL+'?other=1','https://example.com/hms-captain']:
        with pytest.raises(ValueError):candidates([{'key':CAPTAIN_KEY,'url':url}])
    with pytest.raises(ValueError):candidates([{'key':'ss-freshfield-loss','url':CAPTAIN_URL}])


def test_final_story_is_bound_to_exact_incident_and_source_not_just_world_name():
    row=candidates(catalog())[0]
    story={'topic_key':CAPTAIN_KEY,'source':{'url':CAPTAIN_URL},'fiction':False,'visual_plan':{'world':'stormship_inquiry'}}
    validate_source(story,row)
    assert story['director_source_contract']['schematic_not_to_scale'] is True
    for key,value in [('topic_key','franklin-expedition-1845'),('fiction',True),('visual_plan',{'world':'abandoned_station'}),('source',{'url':'https://example.com'})]:
        wrong=deepcopy(story);wrong[key]=value
        with pytest.raises(ValueError):validate_source(wrong,row)


def test_bank_never_mutates_catalog_state():
    original=catalog();before=deepcopy(original)
    result=candidates(original);result[0]['director_contract']['source_requirements'].append('changed locally')
    assert original==before
    assert 'changed locally' not in candidates(original)[0]['director_contract']['source_requirements']


def test_prepare_uses_unused_exact_incident_after_exhausted_legacy_choices(tmp_path):
    root=tmp_path/'professional_motion';root.mkdir()
    (root/'catalog.json').write_text(json.dumps({'horror':catalog()}))
    schema=deepcopy(editorial.SCHEMA);schema['properties']['visual_plan']={'type':'OBJECT'}
    old=[{'topic_key':key} for key in ['franklin-expedition-1845','mary-celeste-1872','endurance-1915','ss-freshfield-loss']]
    expected={'topic_key':CAPTAIN_KEY,'canonical_subject':CAPTAIN_KEY,'title':'الكابتن','source':{'url':CAPTAIN_URL},'fiction':False,'visual_plan':{'world':'stormship_inquiry'}}
    with patch.object(editorial,'ROOT',root),patch.object(editorial,'SCHEMA',schema),patch.object(editorial,'prior',return_value=old),patch.object(editorial,'registry',return_value={'episodes':[]}),patch.object(editorial,'save') as save,patch.object(editorial,'write_sourced',return_value=expected) as write:
        result=editorial.prepare('horror','isolated-test')
    assert result['topic_key']==CAPTAIN_KEY
    assert write.call_args.args[0]['key']==CAPTAIN_KEY
    assert write.call_args.args[0]['director_contract']['world']=='stormship_inquiry'
    assert save.call_args.args[0]['episodes'][0]['topic_key']==CAPTAIN_KEY
    assert json.loads((root/'delivery/story.json').read_text())==expected


def test_reserved_captain_is_not_retried_as_a_new_hash_topic(tmp_path):
    root=tmp_path/'professional_motion';root.mkdir()
    (root/'catalog.json').write_text(json.dumps({'horror':catalog()}))
    schema=deepcopy(editorial.SCHEMA);schema['properties']['visual_plan']={'type':'OBJECT'}
    with patch.object(editorial,'ROOT',root),patch.object(editorial,'SCHEMA',schema),patch.object(editorial,'prior',return_value=[{'topic_key':CAPTAIN_KEY,'url':CAPTAIN_URL}]),patch.object(editorial,'registry',return_value={'episodes':[]}),patch.object(editorial,'write_sourced') as write:
        with pytest.raises(RuntimeError,match='No unused'):
            editorial.prepare('horror','isolated-exhausted')
    write.assert_not_called()
