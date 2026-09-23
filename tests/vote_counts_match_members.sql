select vote_id, party
from {{ ref('gold_party_vote_decisions') }}
where yes_votes + no_votes + abstain_votes + absent_votes <> members_recorded
