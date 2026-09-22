select s.speaker,s.party,w.word,sum(w.occurrences) as occurrences,
       1000.0*sum(w.occurrences)/any_value(t.total_words) as per_1000_words
from {{ source('raw','words') }} w
join {{ ref('stg_speeches') }} s using(speech_id)
join (select speaker,party,sum(word_count) as total_words from {{ ref('stg_speeches') }} where eligible group by speaker,party) t
on s.speaker=t.speaker and s.party=t.party
group by s.speaker,s.party,w.word
