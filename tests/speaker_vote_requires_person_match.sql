select vote_id, speech_id
from {{ ref('gold_decision_speech_links') }}
where same_member <> (speaker_vote is not null)
