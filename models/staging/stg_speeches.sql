select speech_id, dok_id as protocol_id, dok_rm as session,
       try_cast(dok_datum as date) as speech_date,
       cast(substr(dok_rm,1,4) as integer) as session_year,
       speaker, party, parti as original_party, intressent_id as original_person_id,
       talare as original_speaker, replik = 'Y' as is_reply,
       anforandetext as speech_text, word_count, eligible,
       source_url, avsnittsrubrik as debate_title
from {{ source('raw','speeches') }}
