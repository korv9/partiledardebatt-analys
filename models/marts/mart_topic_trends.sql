with counts as (
 select session, session_year, party, topic_id, any_value(topic_label) as topic_label,
        count(*) as segments, sum(word_count) as words
 from {{ ref('int_segments') }} group by session, session_year, party, topic_id
)
select *, 100.0 * words / sum(words) over(partition by session,party) as word_share_pct
from counts
