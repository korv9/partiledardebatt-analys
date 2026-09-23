select
    upper(vote_id) as vote_id,
    session,
    designation,
    try_cast(point as integer) as point,
    member_name,
    member_id,
    case upper(party) when 'FP' then 'L' when 'KDS' then 'KD' else upper(party) end as party,
    party as original_party,
    vote,
    subject,
    try_cast(vote_date as date) as vote_date
from {{ source('raw', 'votes') }}
