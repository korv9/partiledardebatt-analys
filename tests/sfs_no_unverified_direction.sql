select * from {{ ref('gold_sfs_provisions') }}
where temporal_status = 'unverified_snapshot' and direction_eligible
union all by name
select * from {{ ref('gold_sfs_provisions') }}
where valid_from is null and direction_eligible
