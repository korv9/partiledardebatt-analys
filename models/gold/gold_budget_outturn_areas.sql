select
    budget_year, expenditure_area,
    max(expenditure_area_name) as expenditure_area_name,
    count(*) as appropriation_rows,
    sum(coalesce(approved_budget_msek, 0)) as approved_budget_msek,
    sum(coalesce(amendments_msek, 0)) as amendments_msek,
    sum(coalesce(outturn_msek, 0)) as outturn_msek,
    max(source_url) as source_url
from {{ ref('stg_budget_outturn_appropriations') }}
group by budget_year, expenditure_area
