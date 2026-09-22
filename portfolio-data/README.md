# Portfolio-data

Den här katalogen genereras av `python scripts/export_portfolio.py` efter `dbt build`.

Börja med `manifest.json` eller `overview.json`. JSON är avsett för webbsidan och CSV för nedladdning och kontroll.

```javascript
const topics = await fetch('/data/partiledardebatter/topics/summary.json')
  .then(response => response.json());

console.log(topics.data);
```

Alla JSON-filer innehåller `schema_version`, `generated_at` och `data`. UMAP är uppdelad per riksmöte under `sessions/<riksmöte>/umap.json`, med högst 400 deterministiskt valda punkter per fil.

Budgetramar finns i `budgets/summary.json` och per riksmöte i `sessions/<riksmöte>/budgets.json`. `GOV` är regeringens samlade förslag; övriga aktörer är partiernas budgetmotioner.
