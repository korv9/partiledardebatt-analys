select
    l.vote_id,
    v.session,
    l.party,
    v.designation,
    v.point,
    v.vote_date,
    v.title as decision_title,
    v.point_heading,
    v.party_position,
    v.source_url as decision_url,
    l.speech_id,
    s.speaker,
    s.speech_date,
    s.source_url as speech_url,
    substr(s.speech_text, 1, 500) as speech_excerpt,
    round(l.cosine_similarity, 4) as cosine_similarity,
    l.same_member,
    personal_vote.vote as speaker_vote,
    'tematisk textlikhet; ingen slutsats om ståndpunkt' as relation_note
from {{ source('raw', 'decision_speech_links') }} l
join {{ ref('gold_party_vote_decisions') }} v on l.vote_id = v.vote_id and l.party = v.party
join {{ ref('stg_speeches') }} s on l.speech_id = s.speech_id
left join {{ ref('stg_votes') }} personal_vote
    on l.vote_id = personal_vote.vote_id and s.original_person_id = personal_vote.member_id
where s.speech_date <= v.vote_date
