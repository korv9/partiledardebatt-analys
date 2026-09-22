select chunk_id from {{ ref('int_segments') }}
where regexp_matches(text,'(?i)STYLEREF|MERGEFORMAT')
