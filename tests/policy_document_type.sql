select * from {{ ref('gold_policy_documents') }}
where document_type not in ('fr', 'ip', 'prop')
