select
    session,
    budget_year,
    expenditure_area,
    expenditure_area_name,
    actor,
    proposal_type,
    amount_msek,
    deviation_msek,
    round(100.0 * amount_msek / sum(amount_msek) over (partition by session, actor), 4) as budget_share_pct,
    document_id,
    source_url
from {{ ref('stg_budget_frames') }}
where expenditure_area between 1 and 27
