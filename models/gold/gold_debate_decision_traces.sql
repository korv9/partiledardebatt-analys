with party_reservations as (
    select point_id, party, count(distinct reservation_number) as party_reservation_count
    from {{ ref('gold_decision_reservations') }}
    group by point_id, party
)
select
    d.point_id, d.session, d.designation, d.point,
    d.decision_date, d.point_heading, d.proposal_text,
    d.motion_count, d.proposition_count, d.numbered_claim_count,
    d.reservation_count, coalesce(r.party_reservation_count, 0) as party_reservation_count,
    l.party, l.speech_id, l.speaker, l.speech_date,
    l.speech_excerpt, l.speech_url, l.cosine_similarity,
    l.party_position, l.speaker_vote, l.same_member,
    d.vote_id, d.source_url as decision_url,
    'thematic_speech_match' as speech_link_evidence,
    'Citation and reservation counts are direct document data; speech link is thematic only.' as interpretation_note
from {{ ref('gold_decision_speech_links') }} l
join {{ ref('gold_decision_points') }} d on l.vote_id = d.vote_id
left join party_reservations r on d.point_id = r.point_id and l.party = r.party
