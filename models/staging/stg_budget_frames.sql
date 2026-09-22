select
    session,
    budget_year::integer as budget_year,
    expenditure_area::integer as expenditure_area,
    trim(expenditure_area_name) as expenditure_area_name,
    upper(actor) as actor,
    proposal_type,
    government_amount_msek::bigint as government_amount_msek,
    deviation_msek::bigint as deviation_msek,
    amount_msek::bigint as amount_msek,
    document_id,
    source_url
from {{ source('raw', 'budget_frames') }}
