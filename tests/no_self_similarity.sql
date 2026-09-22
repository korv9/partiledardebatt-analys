select speech_id from {{ ref('mart_similar_speeches') }}
where speech_id=neighbor_id or speaker=neighbor_speaker or cosine_similarity>1.00001 or cosine_similarity < -1.00001
