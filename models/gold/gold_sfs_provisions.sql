select
    provision_id, sfs_document_id, provision_suffix,
    kind, label, chapter, heading, provision_order,
    provision_text, text_sha256, document_title,
    snapshot_version, snapshot_retrieved_at,
    source_sha256, source_url,
    valid_from, valid_to, temporal_status,
    false as direction_eligible
from {{ ref('stg_sfs_provisions') }}
