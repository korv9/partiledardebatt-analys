with counts as (
    select
        vote_id, session, designation, point, party,
        count(*) filter (where vote = 'Ja') as yes_votes,
        count(*) filter (where vote = 'Nej') as no_votes,
        count(*) filter (where vote = 'Avstår') as abstain_votes,
        count(*) filter (where vote = 'Frånvarande') as absent_votes,
        count(*) as members_recorded,
        min(vote_date) as vote_date
    from {{ ref('stg_votes') }}
    where party in ('S','M','V','MP','C','L','KD','SD','NYD')
    group by 1,2,3,4,5
), motions as (
    select upper(vote_id) as vote_id, count(distinct motion_id) as cited_motion_count
    from {{ source('raw', 'decision_motions') }}
    group by 1
)
select
    c.*, d.document_id, d.title, d.point_heading, d.proposal_text,
    d.winning_side, coalesce(m.cited_motion_count, 0) as cited_motion_count,
    d.source_url, d.status_url,
    case
        when yes_votes > no_votes and yes_votes > abstain_votes then 'Ja'
        when no_votes > yes_votes and no_votes > abstain_votes then 'Nej'
        when abstain_votes > yes_votes and abstain_votes > no_votes then 'Avstår'
        else 'Delat eller ingen avgiven röst'
    end as party_position
from counts c
join {{ ref('stg_decisions') }} d on c.vote_id = d.vote_id
left join motions m on c.vote_id = m.vote_id
