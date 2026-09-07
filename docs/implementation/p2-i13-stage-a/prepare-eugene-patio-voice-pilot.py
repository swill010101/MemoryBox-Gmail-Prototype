"""Read-only preflight for the bounded Eugene Patio 003 proposal; no media or database writes."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_PERSON_ID = 'b67708d8-0262-404d-a230-2cc99900cea4'
PROPOSAL = ROOT / 'docs/implementation/p2-i13-stage-a/eugene-patio-bounded-voice-pilot-proposal.json'


def load_selection(path: Path = PROPOSAL) -> dict:
    proposal = json.loads(path.read_text(encoding='utf-8-sig'))
    if proposal.get('processing_authorized') is not False or proposal.get('purpose') != 'voice_pilot':
        raise RuntimeError('Proposal is not design-only voice-pilot evidence.')
    spans = proposal.get('selections')
    if not isinstance(spans, list) or len(spans) != 4:
        raise RuntimeError('Proposal must contain exactly four spans.')
    if [span.get('role') for span in spans] != ['training', 'held_out', 'held_out', 'held_out']:
        raise RuntimeError('Proposal span roles changed.')
    if spans[0].get('person_id') not in (None, TARGET_PERSON_ID):
        raise RuntimeError('Training target changed.')
    return proposal


def same_timestamp(actual: object, expected: object) -> bool:
    return abs(float(actual) - float(expected)) <= 0.000001


def validate_rows(proposal: dict, rows: list[dict]) -> dict:
    by_id = {row['annotation_id']: row for row in rows}
    expected = {span['annotation_id']: span for span in proposal['selections']}
    if set(by_id) != set(expected):
        raise RuntimeError('Selected annotations changed or are unavailable.')
    for annotation_id, span in expected.items():
        row = by_id[annotation_id]
        for key in ('version_id', 'source_id', 'provider_key'):
            if row[key] != span[key]:
                raise RuntimeError('Selected annotation identity changed.')
        if not same_timestamp(row['t_start'], span['start']) or not same_timestamp(row['t_end'], span['end']):
            raise RuntimeError('Selected annotation timing changed.')
        if not row['active'] or row['retired']:
            raise RuntimeError('Selected annotation is not active evidence.')
        if annotation_id in {proposal['selections'][0]['annotation_id'], proposal['selections'][1]['annotation_id']}:
            if row['person_id'] != TARGET_PERSON_ID or row['speaker_state'] != 'person' or row['pilot_uses']:
                raise RuntimeError('Patio Eugene evidence is no longer fresh and active.')
        elif annotation_id == proposal['selections'][2]['annotation_id']:
            if row['person_id'] != '33509a4c-0869-458a-b0b9-35a669aace16' or row['speaker_state'] != 'person':
                raise RuntimeError('Tom negative control changed.')
        else:
            if row['person_id'] is not None or row['speaker_state'] != 'unknown':
                raise RuntimeError('Unknown negative control changed.')
    return {
        'work_items': 4,
        'audio_seconds': proposal['budget']['selected_audio_seconds'],
        'training_key': proposal['selections'][0]['key'],
        'held_out_keys': [span['key'] for span in proposal['selections'][1:]],
        'patio_annotations_fresh': True,
    }


def main() -> int:
    if os.environ.get('MEMORYBOX_RECOGNITION_DRAIN') != '0' or os.environ.get('MEMORYBOX_SPEECH_DRAIN') != '0':
        raise RuntimeError('Both drains must be explicitly off.')
    if os.environ.get('MEMORYBOX_I13_ADMISSION_ID'):
        raise RuntimeError('Admission must be unset for preflight.')
    from memorybox.db import connection

    proposal = load_selection()
    ids = [span['annotation_id'] for span in proposal['selections']]
    query = """
    SELECT a.id::text AS annotation_id, a.version_id::text AS version_id,
           v.provider_key, v.source_id, a.t_start, a.t_end,
           a.person_id::text AS person_id, a.speaker_state,
           (active.id IS NOT NULL) AS active,
           (ret.annotation_id IS NOT NULL) AS retired,
           COALESCE(uses.pilot_uses, '[]'::jsonb) AS pilot_uses
    FROM i13_transcript_annotations a
    JOIN i13_transcript_versions v ON v.id=a.version_id
    LEFT JOIN i13_active_annotations active ON active.id=a.id
    LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id=a.id
    LEFT JOIN LATERAL (
      SELECT jsonb_agg(jsonb_build_object('admission_id', ad.id::text, 'key', span->>'key', 'role', span->>'role')) AS pilot_uses
      FROM i13_processing_admissions ad
      CROSS JOIN LATERAL jsonb_array_elements(ad.plan_json->'spans') span
      WHERE ad.plan_json->>'purpose'='voice_pilot' AND span->>'annotation_id'=a.id::text
    ) uses ON true
    WHERE a.id = ANY(%s::uuid[])
    """
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows = [dict(row) for row in conn.execute(query, (ids,)).fetchall()]
    result = validate_rows(proposal, rows)
    print(json.dumps({'ok': True, 'mode': 'check_only', 'private_audio_processed': False,
                      'database_writes': False, 'admission_created': False, **result}, indent=2))
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        # RuntimeError messages in this module are fixed validation labels, never connection details.
        print(json.dumps({'ok': False, 'error_type': 'validation_failed', 'code': str(exc),
                          'message': 'Preflight failed; no media or database writes occurred.'}))
        raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__,
                          'message': 'Preflight failed; no media or database writes occurred.'}))
        raise SystemExit(2)
