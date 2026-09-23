with citations as (
    select point_id,
           count(distinct document_id) filter (where document_type = 'mot') as motion_count,
           count(distinct document_id) filter (where document_type = 'prop') as proposition_count,
           count(*) filter (where claim_scope = 'numbered_claim') as numbered_claim_count
    from {{ ref('stg_decision_citations') }}
    group by point_id
), reservations as (
    select point_id, count(distinct reservation_number) as reservation_count
    from {{ ref('stg_decision_reservations') }}
    group by point_id
)
select p.*, coalesce(c.motion_count, 0) as motion_count,
       coalesce(c.proposition_count, 0) as proposition_count,
       coalesce(c.numbered_claim_count, 0) as numbered_claim_count,
       coalesce(r.reservation_count, 0) as reservation_count,
       case when p.vote_id is null then 'no_recorded_roll_call' else 'recorded_roll_call' end as vote_coverage
from {{ ref('stg_committee_points') }} p
left join citations c on p.point_id = c.point_id
left join reservations r on p.point_id = r.point_id
