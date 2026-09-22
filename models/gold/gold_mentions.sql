select
    speaker,
    party as speaker_party,
    target,
    kind as target_type,
    cast(mentions as bigint) as mentions,
    speeches,
    round(per_1000_words, 4) as per_1000_words
from {{ ref('mart_mentions') }}
where not self_mention
qualify row_number() over (
    partition by party
    order by mentions desc, speaker, target
) <= 200
order by speaker_party, mentions desc
