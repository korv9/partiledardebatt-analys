select
    f.session, f.budget_year, f.expenditure_area,
    f.expenditure_area_name, f.actor, f.proposal_type,
    f.amount_msek as proposed_msek,
    o.approved_budget_msek, o.amendments_msek,
    o.outturn_msek,
    case when o.outturn_msek is not null then o.outturn_msek - f.amount_msek end
        as outturn_minus_proposal_msek,
    f.source_url as proposal_source_url,
    o.source_url as outturn_source_url
from {{ ref('gold_budget_frames') }} f
left join {{ ref('gold_budget_outturn_areas') }} o
  on f.budget_year = o.budget_year and f.expenditure_area = o.expenditure_area
