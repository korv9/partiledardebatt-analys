select a.speech_id,a.neighbor_id,a.cosine_similarity,
       s.speaker,s.party,s.speech_date,s.source_url,
       n.speaker as neighbor_speaker,n.party as neighbor_party,n.speech_date as neighbor_date,n.source_url as neighbor_url,
       s.speech_text,n.speech_text as neighbor_text
from {{ source('raw','similarities') }} a
join {{ ref('stg_speeches') }} s using(speech_id)
join {{ ref('stg_speeches') }} n on a.neighbor_id=n.speech_id
