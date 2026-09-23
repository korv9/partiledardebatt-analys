select
    upper(vote_id) as vote_id,
    session,
    document_id,
    designation,
    try_cast(point as integer) as point,
    title,
    point_heading,
    proposal_text,
    winning_side,
    try_cast(decision_date as date) as decision_date,
    source_url,
    status_url
from {{ source('raw', 'decisions') }}
