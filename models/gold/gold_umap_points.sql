with sampled as (
    select
        chunk_id,
        speech_id,
        topic_id,
        topic_label,
        round(x, 4) as x,
        round(y, 4) as y,
        party,
        speaker,
        session,
        session_year,
        speech_date,
        left(text, 220) as excerpt,
        source_url,
        row_number() over (
            partition by session
            order by hash(chunk_id)
        ) as session_sample_rank,
        count(*) over (partition by session) as session_population
    from {{ ref('int_segments') }}
)
select * exclude(session_sample_rank)
from sampled
where session_sample_rank <= 400
order by session_year, chunk_id
