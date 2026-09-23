select
    point_id, document_id, document_type, document_reference,
    try_cast(claim_number as integer) as claim_number,
    claim_scope, document_title, document_author, document_url
from {{ source('raw', 'decision_citations') }}
