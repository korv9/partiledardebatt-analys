select
    speech_id,
    neighbor_id,
    round(cosine_similarity, 5) as cosine_similarity,
    speaker,
    party,
    speech_date,
    source_url,
    neighbor_speaker,
    neighbor_party,
    neighbor_date,
    neighbor_url,
    left(speech_text, 350) as speech_excerpt,
    left(neighbor_text, 350) as neighbor_excerpt
from {{ ref('mart_similar_speeches') }}
where party <> neighbor_party
qualify row_number() over (
    partition by least(speech_id, neighbor_id), greatest(speech_id, neighbor_id)
    order by cosine_similarity desc
) = 1
order by cosine_similarity desc
limit 500
