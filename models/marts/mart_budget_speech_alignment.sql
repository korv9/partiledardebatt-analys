with speech_hits as (
    select
        s.session,
        s.party as actor,
        k.expenditure_area,
        sum(w.occurrences)::bigint as speech_keyword_occurrences
    from {{ source('raw', 'words') }} w
    join {{ ref('stg_speeches') }} s using (speech_id)
    join {{ ref('budget_area_keywords') }} k on w.word = k.keyword
    where s.eligible
    group by 1, 2, 3
), comparable as (
    select
        b.*,
        coalesce(h.speech_keyword_occurrences, 0) as speech_keyword_occurrences
    from {{ ref('gold_budget_frames') }} b
    left join speech_hits h using (session, actor, expenditure_area)
    where b.actor <> 'GOV'
), shares as (
    select
        *,
        100.0 * speech_keyword_occurrences /
            nullif(sum(speech_keyword_occurrences) over (partition by session, actor), 0)
            as speech_attention_pct
    from comparable
)
select
    *,
    speech_attention_pct - budget_share_pct as attention_minus_budget_pp,
    corr(budget_share_pct, speech_attention_pct)
        over (partition by session, actor) as alignment_correlation
from shares
