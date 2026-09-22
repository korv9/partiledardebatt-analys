select c.*, s.session, s.session_year, s.speech_date, s.speaker, s.party,
       s.protocol_id, s.is_reply, s.source_url, t.label as topic_label
from {{ source('raw','chunks') }} c
join {{ ref('stg_speeches') }} s using(speech_id)
join {{ source('raw','topics') }} t using(topic_id)
