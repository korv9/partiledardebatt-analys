# Resultat från ämnesanalysen

Analysen omfattar 10 148 importerade anföranden från riksmötena 1993/94–2025/26. Efter att talmannens inlägg, mycket korta tal och poster utan ett känt parti filtrerats bort återstår 10 055 anföranden och 39 269 textsegment.

## Huvudresultat

Efter en jämförelse av 21 inställningar används HDBSCAN med `leaf`-urval på den 10-dimensionella UMAP-projektionen. Den ger 25 grupper. Ett kluster med mest korta slutfragment har flyttats till ”Ej grupperade”. Den nya modellen lämnar 60,0 % av segmenten och 59,4 % av orden ogrupperade. Det är ett avsiktligt byte mot tydligare kärnkluster.

| Mått | Tidigare HDBSCAN | Nuvarande modell |
|---|---:|---:|
| Cosinus-silhuett i originalvektorer, urval 2 400 segment | 0,071 | 0,105 |
| Andel segment i grupper | 50,8 % | 40,0 % |
| Största gruppens andel av alla segment | 13,1 % | 3,2 % |
| Justerat Rand-index vid närliggande inställning | 0,924 | 0,983 |

Silhuetten beräknas bara för grupperade segment; förbättringen får alltså inte tolkas utan täckningen. En 20-gruppers KMeans-modell täckte 100 % men fick lägre silhuett (0,055) och mindre stabil indelning mellan två startvärden (ARI 0,50). Den valdes därför inte som huvudresultat.

De största automatiska grupperna, mätt som andel av alla analyserade ord inklusive oklassificerat material, är:

| Automatisk etikett | Andel ord |
|---|---:|
| EU / Europa / europeiska | 3,29 % |
| Kärnkraft / kärnkraften / el | 2,85 % |
| Vården / vård / sjukvården | 2,60 % |
| Jobb / arbetslösheten / arbetsmarknaden | 2,52 % |
| Flyktingar / migrationspolitik / invandring | 2,50 % |
| Partier / politiska / valet | 2,42 % |
| Polisen / poliser / brott | 1,86 % |
| Bostäder / marknadshyror / hyresrätter | 0,64 % |

Etiketterna är maskinellt skapade nyckelord. De finare grupperna skiljer exempelvis klimatpolitik från kärnkraft och bostäder från järnväg. Några grupper fångar debatt om partier och personer snarare än ett budgetområde. Skola, jobb och skatt förekommer i flera närliggande undergrupper; de bör samlas under bredare teman vid summering.

Den interaktiva rapporten visar nu budgetramar intill UMAP-kartan med gemensamt filter för parti och riksmöte. Budgetbeloppen påverkar inte kartans koordinater. De representerar föreslagna pengar medan kartan representerar likhet mellan textsegment.

## Beslut, motioner och röster

För riksmötena 2024/25 och 2025/26 finns nu 507 446 registrerade ledamotsröster från Riksdagens öppna data. De är kopplade till 1 436 voterade punkter i utskottsbetänkanden. Ytterligare 18 voterings-ID saknar en säker matchning till en beslutspunkt och redovisas som luckor, inte som antagna eller avslagna förslag. De matchade punkterna innehåller 5 367 uttryckliga hänvisningar till motioner. En punkt kan behandla flera motioner, ofta med olika yrkanden, så partirösten ska inte tillskrivas varje motion separat.

En tematisk sökning med minst 0,60 i cosinuslikhet gav 933 länkar från beslut till tidigare partiledardebattal inom samma riksmöte och parti. I 602 av dessa länkar kunde även talarens person-ID matchas mot en registrerad röstpost, inklusive frånvaro. Det är antal länkar, inte unika personer. Textlikheten används för att hitta relevanta tal, inte för att avgöra om talaren höll med om förslaget. Rapporten och guldlagret visar röstfördelning, beslutspunkt, motioner och originalkällor sida vid sida. För att bedöma faktisk överensstämmelse mellan ord och handling måste man läsa den exakta beslutstexten, reservationerna och talet.

Det nya ärendelagret innehåller 4 407 punkter från de importerade betänkandena; 2 971 av dem saknar registrerat namnupprop. Det finns 18 505 uttryckliga dokument-/yrkandehänvisningar (en motion kan ge flera numrerade yrkanden), 7 503 reservationsposter per parti och 4 354 dokument med metadata om propositioner, skriftliga frågor eller interpellationer. De 933 talmatchningarna kan nu följas till dessa direkt källbelagda poster i `gold_debate_decision_traces`. Betänkanden utan någon importerad votering ingår ännu inte; inte heller ministrars beslut eller yrkandenas och reservationernas fulltext.

Statskontorets nya utfallslager innehåller 15 643 anslagsrader för 1997–2025. `gold_budget_execution` jämför FiU1-förslag med beslutad budget och faktiskt utfall där årgångarna överlappar. Det är en jämförelse av belopp, inte ett mått på politisk effekt eller en enskild talares ansvar.

Ett separat SFS-lager importerar nu 70 paragrafer och 22 övergångsbestämmelser med verifierad källhash ur Allegorias snapshot av lagen (1982:80) om anställningsskydd (`t.o.m. SFS 2022:836`). En försiktig lagnamnssökning ger 21 talkandidater i hela debattmaterialet, varav fyra under 2020/21. De är inte länkade till en bestämd paragraf. Snapshotens lydelse är inte verifierad som gällande vid talens datum, och ingen `direction`-poäng har beräknats.

De mest uttryckligen omnämnda talarna i hela materialet är Göran Persson (1 671 träffar), Jimmie Åkesson (1 278), Stefan Löfven (1 002), Jan Björklund (856) och Jonas Sjöstedt (851). Fullständiga namn används, självomnämnanden är borttagna och samma omnämnande kan förekomma flera gånger i ett tal. Resultatet gynnar personer som varit aktiva under många debatter.

De mest omnämnda partierna är S (3 429), M (1 871), V (1 719), MP (1 664) och SD (1 498). Ett omnämnande säger inte om sammanhanget är kritik, samarbete eller neutral beskrivning.

När varje parti jämförs med alla övriga framträder bland annat `bredband` för C, `arbetslinje` för M, `kollektivtrafik` för MP, `invandringspolitiken` för SD och `riskkapitalbolagen` för V. Resultaten kräver samma tidsavgränsning för rättvis partijämförelse; partierna täcker olika historiska perioder.

Den semantiska likhetsanalysen hittar närliggande tal över partigränser. De högst rankade paren ligger kring 0,96 i cosinuslikhet. Likhet betyder att språkmodellens sammanfattande vektorer ligger nära varandra, inte att talarna håller med varandra eller att en har kopierat den andra. Rapporten länkar båda originaltalen för manuell granskning.

## Rekommenderad användning

Använd ämneskartan för hypoteser och utforskning. Använd dbt-tabellerna för mätningar, tidsfilter och reproducerbara jämförelser. Varje slutsats bör kontrolleras mot representativa citat och Riksdagens originalprotokoll.

Den interaktiva rapporten finns i `reports/analys.html`. Metod, tabeller, testregler och kända begränsningar finns i `ANALYSIS.md`.
