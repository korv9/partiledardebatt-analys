with totals as (
 select party,sum(word_count) as total_words,count(*) as speeches
 from {{ ref('stg_speeches') }} where eligible group by party
), counts as (
 select s.party,w.word,sum(w.occurrences) as occurrences,count(*) as speeches_with_word
 from {{ source('raw','words') }} w join {{ ref('stg_speeches') }} s using(speech_id)
 group by s.party,w.word
), corpus as (
 select word,sum(occurrences) as corpus_occurrences from counts group by word
)
select c.*, t.total_words,1000.0*c.occurrences/t.total_words as per_1000_words,
       ln(((c.occurrences+0.5)/(t.total_words+1.0)) /
          ((g.corpus_occurrences-c.occurrences+0.5)/
           ((select sum(total_words) from totals)-t.total_words+1.0))) as log_rate_ratio
from counts c join totals t using(party) join corpus g using(word)
