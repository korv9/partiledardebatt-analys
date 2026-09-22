select
    speaker,
    party,
    count(*) as speeches,
    cast(sum(word_count) as bigint) as words,
    min(speech_date) as first_speech_date,
    max(speech_date) as last_speech_date
from {{ ref('stg_speeches') }}
where eligible
group by speaker, party
order by words desc
