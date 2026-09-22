# Analysprojekt

Detta är ett körbart dbt-projekt med DuckDB. Python producerar språkmodellens egenskaper; dbt hanterar SQL-modeller, beroenden och datatester. Originalimporten och SQLite-databasen lämnas oförändrade.

```text
Riksdagens JSON → ingest.py → data/debates.sqlite
  → scripts/features.py → analytics.duckdb / raw
  → dbt staging → intermediate → marts
  → scripts/export_report.py → reports/analys.html
```

## Körning

Från projektmappen, med Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-analysis.txt
# Hämta språkmodell en gång om den inte redan finns lokalt:
.\.venv\Scripts\python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
.\.venv\Scripts\python run_analysis.py
```

Analysen skickar inte debatttexter till en extern modell. GPU används när CUDA finns; annars CPU. Embeddings och UMAP-projektioner återanvänds från `data/features/` om indata är oförändrade. För att tvinga omberäkning efter byte av modell eller parametrar: använd en ny cachekatalog eller ta bort motsvarande genererade cachefiler. Numbaruntime har en projektspecifik cache under `data/numba_cache`.

Enskilda steg:

```powershell
.\.venv\Scripts\python scripts/features.py
.\.venv\Scripts\dbt build --profiles-dir .
.\.venv\Scripts\dbt docs generate --profiles-dir .
.\.venv\Scripts\python scripts/export_report.py
.\.venv\Scripts\python scripts/export_portfolio.py
```

## Tabeller

| Lager | Modell | Innehåll |
|---|---|---|
| raw | speeches, chunks, topics, words, mentions, similarities | Källmetadata och beräknade NLP-egenskaper |
| staging | stg_speeches | Standardiserade namn, partier och datum |
| intermediate | int_segments | Textsegment med ämne, koordinater, talare och källänk |
| marts | mart_topics | Ämnesstorlek, antal tal och andel ord |
| marts | mart_topic_trends | Ämnesandel per parti och riksmöte |
| marts | mart_speaker_topics | Ämnesandel per person/parti |
| marts | mart_word_usage | Ordfrekvens och utmärkande ord per parti |
| marts | mart_speaker_words | Ordfrekvens per person/parti |
| marts | mart_mentions | Riktade omnämnanden och normaliserad frekvens |
| marts | mart_similar_speeches | Närliggande anföranden av andra talare |

SQL-exempel:

```sql
select * from mart_topic_trends where party='MP' order by session,words desc;
select * from mart_word_usage where party='S' and occurrences>=20 order by log_rate_ratio desc limit 20;
select * from mart_mentions where kind='person' and not self_mention order by mentions desc limit 20;
```

## Metod och tolkning

- Samma flerspråkiga modell används för hela historiken. Segmenten omfattar högst 120 modelltoken, med bevarad koppling till tal och källa. Word-fält av typen STYLEREF/MERGEFORMAT och osynliga avstavningstecken rensas före analys. Talmannens inlägg, poster utan ett känt parti och tal kortare än 20 ord filtreras bort. Segment utan ord tas bort. Små slutsegment behålls för täckning.
- UMAP reducerar till 10 dimensioner inför HDBSCAN. En separat 2D-projektion används enbart för kartan. Om HDBSCAN ger färre än åtta grupper eller en grupp med över hälften av segmenten används 24-gruppers KMeans på de ursprungliga normaliserade embeddings. Den faktiskt använda metoden sparas i `data/features/metrics.json`.
- Ämnesetiketter genereras från TF-IDF över gruppernas sammanlagda ord och tvåordsfraser. Detta är en egen ämnespipeline, inte en körning av BERTopic-biblioteket. Nyckelorden är inte manuellt verifierade ämnesnamn. Rapportens citatexempel ligger nära ämnets medelvektor i det ursprungliga modellrummet och kommer från olika talare.
- Känslighetskontrollen jämför alternativa HDBSCAN-parametrar på samma UMAP-projektion eller ett alternativt KMeans-startvärde. ARI ska inte tolkas som kvalitetsbetyg. Den mäter inte stabilitet mellan olika språkmodeller, tidsperioder eller UMAP-startvärden.
- Ämnesandelar beräknas av segmentens ord, inte antalet anföranden. Ett långt tal får därför större vikt än ett kort. Ett segment får ett ämne trots att det kan innehålla flera. Ej grupperade segment ingår i nämnaren.
- Ordfrekvenser beräknas per 1 000 ord i de inkluderade anförandena, inklusive stoppord i nämnaren. Böjningsformer är separata. Listan över stoppord finns i `scripts/features.py`. Utmärkande ord använder en utjämnad frekvenskvot mot övriga partier, inte ett statistiskt signifikanstest. Personnamn kan förekomma bland dessa ord.
- Namn normaliseras genom att ta bort titel och partiparentes. Historiska person-ID:n kan vara felaktiga och används därför inte ensamma för att slå ihop personer. FP→L och KDS→KD är uttrycklig harmonisering; råvärden sparas. Andra fel i källans partibeteckningar rättas inte automatiskt.
- Omnämnanden identifieras med fullständiga namn på talare med minst fem anföranden och uttryckliga partimönster. Efternamn, pronomen och externa personer missas. Partimönster kan fånga adjektiv. Självomnämnanden märks upp och utesluts från rapportens nätverk. Ett omnämnande är inte i sig en attack.
- Liknande tal hittas med cosinuslikhet mellan ordviktade medelvärden av segmentens embeddings. Högst tre andra talare väljs bland de tolv närmaste kandidaterna per tal. Den interaktiva rapporten visar ett begränsat toppurval över partigränser; databasen innehåller fler par. Likhet är inte enighet eller belägg för kopiering.
- Samma tidsperiod bör användas när partier jämförs. Historisk täckning, språkförändringar, källfel och olika talutrymme påverkar resultaten. Rapporten innehåller endast Riksdagens importerade material.

## Kontroller

`dbt build` kontrollerar nycklar, relationer, täckning av analyserade tal, segmentlängd, ändliga koordinater, ämnesandelarnas summa och att likhetspar inte består av samma person. Originalimportens tester körs med `python -m unittest -v`.

Rapporten är fristående och innehåller diagramkoden lokalt. Originaltexter öppnas via länkar till Riksdagen. Den är inte publicerad på internet. Genererade data, modeller och rapportfiler ignoreras av Git.

## Guldlager för portfolio

`scripts/export_portfolio.py` exporterar de färdiga dbt-modellerna till `portfolio-data/`. Katalogen kan kopieras direkt till exempelvis `public/data/partiledardebatter/` i en portfolio.

- `manifest.json` listar varje fil, radantal, storlek och beskrivning.
- `overview.json` innehåller totalsiffror och metodmetadata.
- `topics/summary.json` är den lilla ämnesöversikten.
- `sessions/<riksmöte>/topics.json` och `umap.json` gör att sidan kan ladda en period i taget.
- `parties/<parti>/words.json`, `mentions.json` och `topics.json` gör att sidan kan ladda ett parti i taget.
- `speakers/summary.json` och `similarity/top.json` innehåller talare respektive semantiskt liknande tal.

JSON är avsett för webbgränssnittet. Motsvarande CSV finns för de tabeller där nedladdning och manuell kontroll är användbart. Fulltext, embeddings, råarkiv och databasfiler publiceras inte i guldlagret.

Metodreferenser: [UMAP för klustring](https://umap-learn.readthedocs.io/en/latest/clustering.html), [språkmodell](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [dbt-duckdb](https://github.com/duckdb/dbt-duckdb).
