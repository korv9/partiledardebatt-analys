select
    session,
    session_year,
    party,
    topic_id,
    topic_label,
    segments,
    cast(words as bigint) as words,
    round(word_share_pct, 4) as word_share_pct
from {{ ref('mart_topic_trends') }}
order by session_year, party, words desc
