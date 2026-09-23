with laws as (
    select sfs_document_id, max(document_title) as document_title,
           max(snapshot_version) as snapshot_version,
           max(temporal_status) as temporal_status
    from {{ ref('gold_sfs_provisions') }}
    group by 1
)
select
    s.speech_id, s.session, s.speech_date, s.speaker, s.party,
    s.source_url as speech_url, a.sfs_document_id,
    l.document_title, l.snapshot_version, l.temporal_status,
    a.alias as matched_phrase,
    cast(null as varchar) as provision_id,
    'lexical_law_name_candidate' as link_evidence,
    false as direction_eligible
from {{ ref('stg_speeches') }} s
join {{ ref('sfs_law_aliases') }} a
  on strpos(lower(s.speech_text), lower(a.alias)) > 0
join laws l on a.sfs_document_id = l.sfs_document_id
where s.eligible
