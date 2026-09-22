select
    session,
    budget_year,
    actor as party,
    expenditure_area,
    expenditure_area_name,
    amount_msek,
    deviation_msek,
    round(budget_share_pct, 4) as budget_share_pct,
    speech_keyword_occurrences,
    round(speech_attention_pct, 4) as speech_attention_pct,
    round(attention_minus_budget_pp, 4) as attention_minus_budget_pp,
    round(alignment_correlation, 4) as alignment_correlation,
    source_url
from {{ ref('mart_budget_speech_alignment') }}
where speech_attention_pct is not null
order by budget_year, party, expenditure_area
