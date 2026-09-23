select point_id, document_id, claim_number
from {{ ref('gold_decision_citations') }}
group by 1,2,3
having count(*) > 1
