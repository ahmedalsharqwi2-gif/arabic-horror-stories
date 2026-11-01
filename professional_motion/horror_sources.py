"""Finite source-to-stage contracts for the opt-in documented horror director.

The list is intentionally narrower than the legacy maritime catalog. A physical
HMS Captain model is never a fallback for Franklin, Freshfield or a random feed.
Evidence still comes from the live official article and independent review.
"""
from copy import deepcopy
from urllib.parse import urlparse

CAPTAIN_KEY = 'hms-captain-1870'
CAPTAIN_URL = 'https://www.rmg.co.uk/stories/maritime-history/hms-captain-britains-forgotten-maritime-disaster'
CAPTAIN_CONTRACT = {
    'world': 'stormship_inquiry',
    'supported_topic_keys': [CAPTAIN_KEY],
    'source_url': CAPTAIN_URL,
    'focal_subject': 'The loss of HMS Captain in 1870 and the documented inquiry into its stability',
    'schematic_not_to_scale': True,
    'source_requirements': [
        'Use the official HMS Captain article as evidence, not a general maritime index.',
        'The three-mast/turret ship is HMS Captain only; never depict a different vessel with this model.',
        'Show explanatory stability and weather mechanics only when the article supports them.',
        'The seabed view is an explanatory aftermath, not a claim that this wreck was filmed, found or surveyed.',
        'An archive/evidence table is illustrative; do not invent eyewitness statements, letters, court findings or dialogue.',
        'Lifeboat movement illustrates equipment; do not claim a particular rescue, launch or casualty count absent source support.',
    ],
    'forbidden_claims': [
        'a modern sonar or camera discovery of the wreck',
        'a generic shipwreck with an HMS Captain exterior',
        'ghosts, supernatural causes or invented crew speech',
        'precise dimensions or measured reconstruction inferred from the schematic renderer',
    ],
}


def candidates(rows):
    """Return only a source with the executable documented world already present."""
    result = []
    for row in rows:
        if row.get('key') != CAPTAIN_KEY:
            continue
        parsed = urlparse(row.get('url', ''))
        if (parsed.scheme != 'https' or parsed.hostname != 'www.rmg.co.uk' or
                parsed.username or parsed.password or parsed.port not in (None, 443) or
                parsed.path.rstrip('/') != urlparse(CAPTAIN_URL).path or parsed.query or parsed.fragment):
            raise ValueError('HMS Captain director requires its exact official source URL')
        item = deepcopy(row)
        item['director_contract'] = deepcopy(CAPTAIN_CONTRACT)
        result.append(item)
    if not result:
        raise ValueError('No source is supported by the implemented documented horror director; add a verified source and its exact assets first')
    return result


def validate_source(story, row):
    """Bind final editorial output to the exact non-fiction runtime world."""
    contract = row.get('director_contract')
    if not contract:
        return
    if (story.get('topic_key') != CAPTAIN_KEY or story.get('source', {}).get('url') != CAPTAIN_URL or
            story.get('fiction') is not False or story.get('visual_plan', {}).get('world') != contract['world']):
        raise ValueError('Documented horror source, incident and executable visual world must agree')
    story['director_source_contract'] = deepcopy(contract)
