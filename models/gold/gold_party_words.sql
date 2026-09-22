with ranked as (
    select
        party,
        word,
        occurrences,
        speeches_with_word,
        round(per_1000_words, 4) as per_1000_words,
        round(exp(log_rate_ratio), 4) as frequency_ratio,
        row_number() over (partition by party order by occurrences desc, word) as common_rank,
        row_number() over (
            partition by party
            order by case when occurrences >= 20 then log_rate_ratio end desc nulls last, word
        ) as distinctive_rank
    from {{ ref('mart_word_usage') }}
)
select * from ranked
where common_rank <= 50 or distinctive_rank <= 50
order by party, least(common_rank, distinctive_rank), word
