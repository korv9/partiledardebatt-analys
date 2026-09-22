select
    topic_id,
    topic_label,
    segments,
    speeches,
    cast(words as bigint) as words,
    round(word_share_pct, 4) as word_share_pct,
    topic_id = -1 as is_unclustered
from {{ ref('mart_topics') }}
order by words desc
