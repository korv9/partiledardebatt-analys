select session,party,sum(word_share_pct) as total
from {{ ref('mart_topic_trends') }}
group by session,party having abs(sum(word_share_pct)-100)>0.00001
