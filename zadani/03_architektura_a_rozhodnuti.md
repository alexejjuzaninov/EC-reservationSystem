# C03 · Architektura a rozhodnutí

## Zvolený scénář a AS-IS

**Scénář:** vlastník schválí žádost řidiče o soukromou stanici podle [C02](02_specifikace_operaci.md), BR-04/05/06, pracovní baseline v0.2/V22. [AS-IS diagram](diagramy/00_as_is.png) ukazuje nynější kód. Před V22 rezervace přecházela rovnou do `CONFIRMED`.

| Krok a alternativa | Skutečná realizace a důkaz |
|---|---|
| přijmout rozhodnutí a aktéra | `ApiController.decideBooking()` předá `approve` a demo identitu do `BookingService.decide()` |
| načíst a uzamknout žádost | `BookingService.decide()` zamkne rozvrh stanice a řádek `reservation.bookings FOR UPDATE` |
| ověřit vlastníka a stav | stejná metoda odmítne cizího aktéra 403 a jiný než `PENDING_APPROVAL` stav 409 |
| znovu ověřit slot | `StationService.get()` a `BookingService.availability()` ověří stanici, hodiny, blokace a kolizi |
| změnit stav a vydat událost | `BookingService.decide()` uloží `CONFIRMED` a `BOOKED` v rezervační transakci; `NotificationService`/`BillingPreview` zpracují outbox později |
| kolize při schválení | dostupnost nebo GiST omezení vrátí 409; žádost zůstane čekající; [ověření souběhu](dukazy/overeni_paralelniho_schvaleni.txt) dalo 200/409 |

Stav vlastní tabulka `reservation.bookings`; jediný Java zapisovatel stavu je `BookingService`. Pravidlo nepřekryvu kontroluje aplikace před zápisem a PostgreSQL constraint `no_overlapping_confirmed_bookings` při zápisu. Závislosti scénáře jsou katalogová data stanice, rezervační PostgreSQL a zpracování outboxu; externí platba a OCPP nejsou zapojené.

## Drivery a odpovědnosti

| Driver / zdroj | Proč mění návrh | Otázka pro architekturu |
|---|---|---|
| BR-04, paralelní schválení | dva souběžné pokusy mohou oba předběžně vidět volno | kdo atomicky rozhodne o `CONFIRMED`? |
| BR-05 a stav `PENDING_APPROVAL` | rozhodnutí přijde po skončení původního requestu | kdo vlastní trvalý stav a přechod? |
| BR-06 a outbox | selhání oznámení nesmí vytvořit nebo zrušit rezervaci | kde končí transakce a kdo doručuje událost? |
| rozsah mapy z C01 | velký prostorový katalog zatěžuje čtení jinak než rezervace | které čtení lze oddělit od zápisu slotu? |
| soukromí a role z C01 | přístupový pokyn patří jen potvrzenému řidiči | kdo kontroluje oprávnění a zveřejnění údajů? |

| Odpovědnost | Hlavní vlastník v cíli | Seskupení / oddělení |
|---|---|---|
| identita aktéra a role | Profily | oddělit od stavu rezervace |
| údaje stanice, hodiny, politika | Katalog | oddělit od alokace slotu |
| rozhodnutí o slotu, lifecycle a schválení | Rezervace | držet spolu; jediný vlastník BR-04/05 |
| transakční zápis stavu a outboxu | Rezervace | stejná transakce jako rozhodnutí |
| zobrazení plateb a provize | Platby | oddělit; zpracovat pouze `BOOKED` |
| doručení oznámení | Notifikace | oddělit kvůli selhání doručení |

**Rozhodovací otázka:** jak oddělit katalog, platby a oznámení pro různé zatížení a selhání, aniž by se rozhodnutí o potvrzení a nepřekryvu rozdělilo mezi služby?

## Varianty a ADR-01

| Kritérium z driverů | A · modulární aplikace | B · doménové mikroservisy |
|---|---|---|
| BR-04: nepřekryv | jedna rezervační transakce a DB constraint | stejná záruka uvnitř služby Rezervace; jiné služby nesmějí zapisovat slot |
| schválení po requestu | stav trvá v jedné DB | stav trvá v DB Rezervací; katalog dodá jen politiku stanice |
| výpadek oznámení | lokální outbox a pozdější doručení | outbox → broker → samostatná služba Notifikace; potřebná idempotence |
| velký katalog | jedna aplikace sdílí kapacitu s rezervacemi | Katalog a mapu lze škálovat samostatně |
| provoz a změny | jednodušší nasazení a kontrakty | více procesů, verzování událostí a asynchronní konzistence |

**Průchod stejného scénáře:**

| Krok | A · prototyp | B · cíl |
|---|---|---|
| řidič potvrdí návrh | `BookingService` uloží `PENDING_APPROVAL` | Rezervace uloží stejný stav do svého schématu |
| request skončí, vlastník přijde později | stav zůstává v PostgreSQL | stav zůstává v DB Rezervací; událost je dostupná Notifikacím |
| vlastník schválí | `BookingService` ověří slot a uloží `CONFIRMED` | Rezervace provede totéž jako jediný vlastník slotu |
| druhé souběžné schválení | GiST odmítne kolizi 409 | stejný DB invariant; broker nemá právo rozhodnout o slotu |

**ADR-01 — vlastnictví rezervace.** Kontext: katalog, oznámení a rezervace mají odlišnou zátěž a režim selhání; BR-04 musí být atomické. Rozhodnutí: **B** je cílová architektura, **A** zůstává funkční prototyp. Rezervační služba jediná vlastní lifecycle, schválení a přidělení slotu. Outbox vzniká v téže transakci; další domény se aktualizují asynchronně. Přijaté negativní důsledky: více procesů a kontraktů, zpoždění projekcí, nutná idempotence. Rozhodnutí otevřít znovu, pokud samostatné škálování nepřinese dostatečný přínos proti provozním nákladům.

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

| Přechod ze statechartu C02 | Vlastník rozhodnutí | Kdo jen žádá |
|---|---|---|
| `DRAFT → PENDING_APPROVAL` | Rezervace | řidič, katalog dodá politiku |
| `DRAFT → CONFIRMED` | Rezervace | řidič |
| `PENDING_APPROVAL → CONFIRMED/REJECTED` | Rezervace | vlastník stanice |
| `PENDING_APPROVAL → EXPIRED` | Rezervace | časový proces |
| `CONFIRMED → CANCELLED` | Rezervace | řidič, vlastník nebo správce |

**Runtime mapping:** [prototyp](diagramy/13_runtime_prototyp.png) má jeden Spring Boot proces s `ApiController`, `BookingService`, `StationService`, `NotificationService` a `BillingPreview`; zapisuje do PostgreSQL, mapu čte z PostGIS repliky a clustery ukládá do Redis. [Cílové nasazení](diagramy/02_nasazeni.png) rozděluje stejné odpovědnosti do samostatných služeb za API gateway.

## Konzistentní pohledy

| Pohled | Diagram | Význam |
|---|---|---|
| Kontext | [11 · kontext](diagramy/11_kontext.png) | aktéři a externí systémy |
| Struktura AS-IS | [00 · prototyp](diagramy/00_as_is.png) | konkrétní cesta v kódu |
| Struktura TO-BE | [01 · mikroservisy](diagramy/01_architektura.png) | hranice a vlastnictví dat |
| Nasazení AS-IS | [13 · runtime prototypu](diagramy/13_runtime_prototyp.png) | skutečná hranice procesu a datových služeb |
| Nasazení TO-BE | [02 · cílové nasazení](diagramy/02_nasazeni.png) | plánované samostatné procesy |
| Statika jednotky | [06 · komponenty](diagramy/06_komponenty.png) | vlastníci odpovědností a závislosti |
| Dynamika | [07 · sekvence](diagramy/07_sekvence.png) | žádost a schválení |
| Doména | [10 · doménové třídy](diagramy/10_domena.png) | entity a reference bez implementačních prvků |
| Návrh | [12 · návrhové třídy](diagramy/12_navrhove_tridy.png) | metody a rozhraní odpovídající sekvenci |

## Konzistence návrhu

| Vazba | Architektonická vazba |
|---|---|
| C02 ↔ vlastník přechodu | BR-04/05/06 má jediného vlastníka v Rezervacích; Katalog jen poskytuje politiku |
| komponenty ↔ sekvence ↔ návrhové třídy | API, Rezervace, Katalog, DB a outbox mají stejný směr interakcí; konfliktní větev vrací 409 |
| statechart ↔ sekvence | `PENDING_APPROVAL` vzniká bez obsazení slotu; `CONFIRMED` po opakované kontrole |
| komponenty ↔ runtime | logické role jsou v prototypu moduly jednoho procesu; cílové služby jsou návrh |
| ADR ↔ kód | invariant a outbox v rezervační transakci jsou realizované; samostatné služby zatím ne |

| Oblast | AS-IS → přijatý návrh | Akce a stav |
|---|---|---|
| schvalování vlastníkem | chybělo před V22 → Rezervace rozhoduje o žádosti | **CHANGE:** implementováno ve V22 a `BookingService.decide()` |
| nepřekryv slotu | zámek a GiST constraint → stejný autoritativní invariant | **KEEP:** zachováno |
| událost po změně stavu | transakční outbox → stejný princip před brokerem | **KEEP:** zachováno |
| vlastnictví zápisů | očekává se pouze Rezervace → nutná kontrola všech zápisů | **VERIFY:** statická kontrola níže |

**Pravidlo AR-01:** stav rezervace mění v aplikačním kódu jen rezervační doména; žádná cesta nesmí potvrdit překrývající se slot mimo rezervační transakci. Opakovatelná statická kontrola `rg -n 'INSERT INTO reservation\.bookings|UPDATE reservation\.bookings|DELETE FROM reservation\.bookings' src/main/java` našla zápisy pouze v `booking/BookingService.java`. [Paralelní ověření](dukazy/overeni_paralelniho_schvaleni.txt) dalo 200/409 a právě jeden `CONFIRMED` v DB. **AR-02:** `REQUESTED` a `REJECTED` nesmějí vytvořit platbu; DB oracle je v [C05](05_detailni_navrh_a_testy.md).

Prototyp realizuje rezervační invariant a transakční outbox. Samostatné mikroservisy představují cílový stav.
