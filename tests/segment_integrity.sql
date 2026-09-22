select chunk_id from {{ ref('int_segments') }}
where model_tokens>120 or model_tokens<1 or word_count<1 or not isfinite(x) or not isfinite(y)
