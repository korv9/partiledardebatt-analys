select vote_id, speech_id
from {{ ref('gold_decision_speech_links') }}
where speech_date > vote_date
