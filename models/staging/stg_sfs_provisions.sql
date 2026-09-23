select
    provision_id, sfs_document_id, provision_suffix,
    kind, label, chapter, heading, provision_order::integer as provision_order,
    text as provision_text, text_sha256,
    document_title, snapshot_version,
    try_cast(snapshot_retrieved_at as timestamptz) as snapshot_retrieved_at,
    source_sha256, source_url,
    try_cast(valid_from as date) as valid_from,
    try_cast(valid_to as date) as valid_to,
    temporal_status
from {{ source('raw', 'sfs_provisions') }}
