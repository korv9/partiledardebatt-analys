select
    point_id, session, document_id, designation,
    try_cast(point as integer) as point,
    title, point_heading, proposal_text, decision_type,
    nullif(upper(vote_id), '') as vote_id,
    winning_side, try_cast(decision_date as date) as decision_date,
    source_url
from {{ source('raw', 'committee_points') }}
