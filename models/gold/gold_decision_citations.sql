select
    c.point_id, p.session, p.designation, p.point,
    p.decision_date, p.vote_id, c.document_id,
    c.document_type, c.document_reference, c.claim_number,
    c.claim_scope, c.document_title, c.document_author,
    c.document_url, p.source_url as committee_url,
    'explicit_citation' as link_evidence
from {{ ref('stg_decision_citations') }} c
join {{ ref('stg_committee_points') }} p on c.point_id = p.point_id
