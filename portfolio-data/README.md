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

Budgeten kan visas intill UMAP-kartan med samma filter för parti och riksmöte. Beloppen är inte koordinater i den semantiska kartan.

`votes/summary.json` och `sessions/<riksmöte>/votes.json` visar registrerade röster per parti och beslutspunkt. `decision-motions.json` innehåller bara motioner som uttryckligen nämns i just den beslutspunkten. En röst gäller beslutspunkten, inte varje motion var för sig.

`decision-speech-links.json` kopplar beslut till tidigare tal från samma parti via textlikhet. Länken säger inget om talarens ståndpunkt i sakfrågan.

`decisions/`, `activities/` och `budgets/outturn-areas.json` innehåller nya spårbara lager. Öppna `sessions/<riksmöte>/decisions/index.json` först och ladda sedan filer per utskott. En `citation` är en uttrycklig dokument- eller numrerad yrkandehänvisning i utskottets förslag; en reservation är registrerad för en beslutspunkt. Inget av detta är en automatisk bedömning av ett partis stöd. Budgetutfall är verkliga utgifter, inte ett effektmått.

`laws/index.json` och `laws/<SFS-ID>/provisions.json` innehåller full bestämmelsetext från versionsmärkta SFS-snapshots som verifierats mot Allegorias källhashar. `laws/mentions.json` är enbart lexikala träffar på lagnamn i tal; ingen paragraf eller giltig lydelse vid taldatum har verifierats och inga direction-poäng beräknas.
