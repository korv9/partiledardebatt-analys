# Koppla debattal till SFS utan att förväxla ämne med rättsligt påstående

## Det som finns

`sfs_bridge.py` läser valda SFS-dokument från ett lokalt Allegoria-repo. Allegorias adapter kontrollerar original-XML, bronzesnapshot och parserresultat; debattprojektet sparar bestämmelsetext, käll- och texthash, snapshotversion och källänk i `raw.sfs_provisions`. dbt publicerar `gold_sfs_provisions` och små JSON-filer under `portfolio-data/laws/`.

Första importen är `sfs-1982-80` (lagen om anställningsskydd), 70 paragrafer och 22 övergångsbestämmelser. `gold_sfs_law_mentions` använder en granskbar aliaslista i `seeds/sfs_law_aliases.csv` för att hitta tal som *nämner lagnamnet*. Dessa rader har tom `provision_id` och `direction_eligible=false`. De är kandidater för manuell granskning, inte tal→paragraf-länkar.

## Vad en riktig tal→paragraf-länk behöver

En granskad länk bör ha minst `speech_id`, exakt talcitat, citatets SHA-256, `provision_id`, SFS-källhash, taldatum, kontrollerad lydelses giltighetsintervall, påståendetyp och granskarens motivering. Påståendetyp skiljer exempelvis *beskrivning av gällande rätt* från *förslag om ändring* och *allmän politisk värdering*. Bara den första typen kan utan vidare jämföras med då gällande lagtext. Ett förslag om ändring kräver en separat före/efter-jämförelse.

`valid_from` och `valid_to` är avsiktligt tomma i nuvarande SFS-lager. En sammanställd lagtext med versionsetiketten `t.o.m. SFS 2022:836` bevisar inte vilken lydelse varje paragraf hade under ett tal 2020. Hämta historisk lydelse och verifiera paragrafens ändringshistorik innan en sådan länk markeras som tidsmässigt godkänd.

Allegorias `corpus/law_probe_v1.yaml` innehåller utkast till normativa slots för **omskrivning av lagtext**. Det är inte i sig en annotering av politikers tal. Allegorias `DIRECTION.md` specificerar måttet, men aktuell kod implementerar ännu ingen direction-beräkning. En framtida tal↔lag-analys behöver därför både granskade länkar, mänskligt kontrollerade slots och ett separat validerat jämförelseprotokoll. Ingen poäng visas i portfolion förrän dessa delar finns.

## Körning

```powershell
python sfs_bridge.py --allegoria-root ..\allegoria --document-id sfs-1982-80
.\.venv\Scripts\dbt build --profiles-dir .
python scripts/export_portfolio.py
```

Lägg till fler `--document-id` för snapshots som redan finns i Allegoria. Varje körning ersätter det lokala SFS-lagret med just de angivna dokumenten; ange därför alla dokument som ska finnas kvar.
