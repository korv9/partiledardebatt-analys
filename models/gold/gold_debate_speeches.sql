select
    speech_id, protocol_id, session, speech_date, speech_number,
    debate_title, speaker, original_speaker, party, original_party,
    original_person_id, is_reply, original_reply_code,
    speech_text, word_count, eligible, source_url
from {{ ref('stg_speeches') }}
