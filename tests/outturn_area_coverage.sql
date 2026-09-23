select budget_year
from {{ ref('gold_budget_outturn_areas') }}
group by budget_year
having count(*) != 27
