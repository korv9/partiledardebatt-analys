select s.speech_id from {{ ref('stg_speeches') }} s
left join {{ ref('int_segments') }} c using(speech_id)
where s.eligible and c.chunk_id is null
