select
    point_id, try_cast(reservation_number as integer) as reservation_number,
    upper(party) as party, proposal_type, heading, source_url
from {{ source('raw', 'decision_reservations') }}
