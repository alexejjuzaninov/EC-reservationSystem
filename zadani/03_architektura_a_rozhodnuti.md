# C03 · Architektura a rozhodnutí

## Zvolený scénář a AS-IS

Řidič žádá o nabíjení na soukromé stanici; vlastník rozhoduje před začátkem termínu. [AS-IS diagram](diagramy/00_as_is.png) zachycuje současnou realizaci, nikoli plán: web volá `ApiController`, ten `BookingService.create/confirm/decide`; služba kontroluje stanici, v transakci mění rezervaci v PostgreSQL a zapisuje outbox. `NotificationService` a `BillingPreview` zpracují událost. Před V22 chyběl krok rozhodnutí vlastníka a rezervace přecházela rovnou do `CONFIRMED`.

| Driver | Architektonický důsledek |
|---|---|
| Správnost souběhu | jediný vlastník přechodu do `CONFIRMED`; atomická kontrola slotu |
| Soukromí a role | vlastník rozhoduje jen o své stanici; přístupový pokyn až po potvrzení |
| Auditovatelnost | stav, aktér, čas a outbox událost v jedné transakci |
| Velký katalog | prostorové čtení mapy z PostGIS repliky; Redis pro clustery |
| Vývoj produktu | hranice domén umožňují pozdější samostatné nasazení |

## Varianty a ADR-01

| Varianta | Přínos | Negativní důsledek |
|---|---|---|
| A · modulární aplikace | jednoduchý prototyp, jedna transakční hranice | služby nelze škálovat a vydávat samostatně |
| B · doménové mikroservisy | oddělené týmy, nasazení a zátěž katalogu/rezervací | složitější provoz, verzování kontraktů a asynchronní konzistence |

**Rozhodnutí:** cílová architektura je **B**; funkční prototyp zůstává **A**. Rezervační služba je jediným vlastníkem stavu rezervace a přidělení slotu. Události do dalších domén odcházejí až po transakčním zápisu outboxu. Rozhodnutí přehodnotit, pokud provozní náklady samostatných služeb převýší přínos odděleného škálování. Cílový návrh není vydáván za implementovaný stav.

## Cílové hranice

| Služba | Vlastní data | Rozhraní |
|---|---|---|
| Profily | účty, role, vlastníci | identita aktéra |
| Katalog | stanice, poloha, ceník, politika schvalování | vyhledání a dostupnost stanice |
| Rezervace | návrh, interval, stav, outbox | vytvoření, potvrzení, rozhodnutí, zrušení |
| Platby | účetní záznam, provize, payout | událost `BOOKED` / `CANCELLED` |
| Notifikace | doručené zprávy | doménové události |
| Provoz | telemetrie a metriky | provozní přehled |

Služby vlastní svá schémata a DB role; mezi doménami nejsou cizí klíče ani doménové JOINy. Vazby používají UUID a snapshot ceny/místa v rezervaci. Jeden PostgreSQL primary zajišťuje zápisy, PostGIS replika čtení mapy; Redis drží úrovně clusterů. Kafka je cílový broker, v prototypu je tok událostí simulován lokálním outboxem.

## Konzistentní pohledy

| Pohled | Diagram | Význam |
|---|---|---|
| Kontext | [11 · kontext](diagramy/11_kontext.png) | aktéři a externí systémy |
| Struktura AS-IS | [00 · prototyp](diagramy/00_as_is.png) | konkrétní cesta v kódu |
| Struktura TO-BE | [01 · mikroservisy](diagramy/01_architektura.png) | hranice a vlastnictví dat |
| Nasazení | [02 · cílové nasazení](diagramy/02_nasazeni.png) | logické uzly bez provozních detailů |
| Statika jednotky | [06 · komponenty](diagramy/06_komponenty.png) | `BookingService` a závislosti |
| Dynamika | [07 · sekvence](diagramy/07_sekvence.png) | žádost a schválení |
| Doména | [10 · třídy](diagramy/10_domena.png) | entity a reference |

**Pravidlo AR-01:** žádná cesta nesmí potvrdit překrývající se slot mimo rezervační transakci. V prototypu jej vynucují zámek stanice a GiST exclusion constraint; [paralelní ověření](dukazy/overeni_paralelniho_schvaleni.txt) dalo 200/409 a právě jeden `CONFIRMED`. **AR-02:** `REQUESTED` a `REJECTED` nesmějí vytvořit platbu; ověřeno nezávislým dotazem v [C05](05_detailni_navrh_a_testy.md).
