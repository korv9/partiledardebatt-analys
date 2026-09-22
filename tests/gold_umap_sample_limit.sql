select session, count(*) as points
from {{ ref('gold_umap_points') }}
group by session
having count(*) > 400
