select
    r.point_id, p.session, p.designation, p.point,
    r.reservation_number, r.party, r.proposal_type,
    r.heading, p.vote_id, r.source_url
from {{ ref('stg_decision_reservations') }} r
join {{ ref('stg_committee_points') }} p on r.point_id = p.point_id
