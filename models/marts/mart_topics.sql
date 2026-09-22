select topic_id, any_value(topic_label) as topic_label,
       count(*) as segments, count(distinct speech_id) as speeches,
       sum(word_count) as words,
       100.0 * sum(word_count) / sum(sum(word_count)) over() as word_share_pct
from {{ ref('int_segments') }} group by topic_id
