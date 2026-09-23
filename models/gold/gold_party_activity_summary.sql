with documents as (
    select session, actor_party as party,
           count(*) filter (where document_type = 'fr') as written_questions,
           count(*) filter (where document_type = 'ip') as interpellations
    from {{ ref('stg_policy_documents') }}
    where actor_party is not null
    group by 1,2
), speeches as (
    select session, party, count(*) as debate_speeches
    from {{ ref('stg_speeches') }}
    where eligible
    group by 1,2
)
select coalesce(d.session, s.session) as session,
       coalesce(d.party, s.party) as party,
       coalesce(d.written_questions, 0) as written_questions,
       coalesce(d.interpellations, 0) as interpellations,
       coalesce(s.debate_speeches, 0) as debate_speeches
from documents d
full outer join speeches s on d.session = s.session and d.party = s.party
where coalesce(d.session, s.session) in (select distinct session from documents)
