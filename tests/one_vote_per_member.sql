select vote_id, member_id
from {{ ref('stg_votes') }}
group by 1,2
having count(*) > 1
