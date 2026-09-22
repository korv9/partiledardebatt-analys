select s.speaker,s.party,m.target,m.kind,m.self_mention,
       sum(m.occurrences) as mentions,count(distinct s.speech_id) as speeches,
       1000.0*sum(m.occurrences)/any_value(t.words) as per_1000_words
from {{ source('raw','mentions') }} m
join {{ ref('stg_speeches') }} s using(speech_id)
join (select speaker,party,sum(word_count) as words from {{ ref('stg_speeches') }} where eligible group by speaker,party) t
on s.speaker=t.speaker and s.party=t.party
group by s.speaker,s.party,m.target,m.kind,m.self_mention
