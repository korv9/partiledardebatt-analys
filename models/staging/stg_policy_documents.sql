select
    document_id, session, document_type, designation,
    try_cast(document_date as date) as document_date,
    title, subtitle, nullif(upper(actor_party), '') as actor_party,
    nullif(government_department, '') as government_department,
    status, source_url
from {{ source('raw', 'policy_documents') }}
