select
    budget_year::integer as budget_year,
    expenditure_area::integer as expenditure_area,
    expenditure_area_name,
    appropriation_code, appropriation_name,
    approved_budget_msek::double as approved_budget_msek,
    amendments_msek::double as amendments_msek,
    outturn_msek::double as outturn_msek,
    source_url
from {{ source('raw', 'budget_outturn_appropriations') }}
where expenditure_area between 1 and 27
