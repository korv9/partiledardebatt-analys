# Resultat från första ämnesanalysen

Analysen omfattar 10 148 importerade anföranden från riksmötena 1993/94–2025/26. Efter att talmannens inlägg, mycket korta tal och poster utan ett känt parti filtrerats bort återstår 10 055 anföranden och 39 269 textsegment.

## Huvudresultat

HDBSCAN identifierar 25 ämnesgrupper. 49,2 procent av orden ligger i segment som modellen lämnar oklassificerade. Det gör ämnesandelarna försiktiga: materialet tvingas inte in i kategorier som modellen är osäker på. En känslighetskontroll med andra klusterinställningar ger justerat Rand-index 0,92.

De största automatiska grupperna, mätt som andel av alla analyserade ord inklusive oklassificerat material, är:

| Automatisk etikett | Andel ord |
|---|---:|
| utsläppen / EU / kärnkraft | 13,26 % |
| skolan / lärare / skola | 4,92 % |
| EU / Europa / europeiska | 3,06 % |
| jobb / arbetslösheten / arbetsmarknaden | 2,65 % |
| migrationspolitik / flyktingar / invandring | 2,45 % |
| vården / vård / sjukvården | 2,30 % |
| kvinnor / män / kvinnors | 2,29 % |
| polisen / brott / poliser | 1,87 % |

Etiketterna är maskinellt skapade nyckelord. Den stora gruppen om utsläpp, EU och kärnkraft är bred och bör tolkas som ett sammanhängande semantiskt område, inte som ett färdigt manuellt kodat ämne.

Över tid får flera grupper tydliga toppar: skola 2001/02, migration 2015/16, brott och polis 2020/21 och energi/klimat 2022/23. Detta beskriver textandel i de importerade debatterna, inte väljarnas prioriteringar eller partiernas ståndpunkter.

De mest uttryckligen omnämnda talarna i hela materialet är Göran Persson (1 671 träffar), Jimmie Åkesson (1 278), Stefan Löfven (1 002), Jan Björklund (856) och Jonas Sjöstedt (851). Fullständiga namn används, självomnämnanden är borttagna och samma omnämnande kan förekomma flera gånger i ett tal. Resultatet gynnar personer som varit aktiva under många debatter.

De mest omnämnda partierna är S (3 429), M (1 871), V (1 719), MP (1 664) och SD (1 498). Ett omnämnande säger inte om sammanhanget är kritik, samarbete eller neutral beskrivning.

När varje parti jämförs med alla övriga framträder bland annat `bredband` för C, `arbetslinje` för M, `kollektivtrafik` för MP, `invandringspolitiken` för SD och `riskkapitalbolagen` för V. Resultaten kräver samma tidsavgränsning för rättvis partijämförelse; partierna täcker olika historiska perioder.

Den semantiska likhetsanalysen hittar närliggande tal över partigränser. De högst rankade paren ligger kring 0,96 i cosinuslikhet. Likhet betyder att språkmodellens sammanfattande vektorer ligger nära varandra, inte att talarna håller med varandra eller att en har kopierat den andra. Rapporten länkar båda originaltalen för manuell granskning.

## Rekommenderad användning

Använd ämneskartan för hypoteser och utforskning. Använd dbt-tabellerna för mätningar, tidsfilter och reproducerbara jämförelser. Varje slutsats bör kontrolleras mot representativa citat och Riksdagens originalprotokoll.

Den interaktiva rapporten finns i `reports/analys.html`. Metod, tabeller, testregler och kända begränsningar finns i `ANALYSIS.md`.
