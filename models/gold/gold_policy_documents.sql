select
    d.document_id, d.session, d.document_type, d.designation,
    d.document_date, d.title, d.subtitle, d.actor_party,
    d.government_department, d.status, d.source_url,
    coalesce(c.decision_point_count, 0) as explicitly_cited_decision_points
from {{ ref('stg_policy_documents') }} d
left join (
    select document_id, count(distinct point_id) as decision_point_count
    from {{ ref('stg_decision_citations') }}
    group by document_id
) c on d.document_id = c.document_id
