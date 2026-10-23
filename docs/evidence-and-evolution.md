# Evidence and Evolution

## C01 Engineering Spike

Kód spike je ve složce `spike/`, postup spuštění je v `README.md`, část Rychlý start.

| Položka | Obsah |
|---|---|
| Question / unknown | Udrží kontrola překryvu v service vrstvě pravidlo BR-02 (potvrzené rezervace téže stanice se nepřekrývají), i když dvě potvrzení proběhnou souběžně? |
| What we did | PostgreSQL 16 v Dockeru, entity v SQLAlchemy a service vrstva s kontrolou překryvu. `test_overlap.py` ověří sekvenční případ a perzistenci po novém načtení v jiné session. `test_concurrency_risk.py` pustí dvě potvrzení překrývajících se rezervací ve dvou vláknech a bariérou zajistí, že obě dokončí kontrolu překryvu dřív, než kterékoli zapíše. Spuštěno přes pytest. |
| Observed result | Sekvenčně: překryv odmítnut, navazující rezervace potvrzena, stav po novém načtení trvá. Souběžně: obě rezervace skončí CONFIRMED (`AssertionError: assert 2 == 1`). Kontrola v aplikaci pravidlo při souběhu neudrží, protože databáze sama žádné omezení nemá. |
| Decision / what changes | BR-02 vynucuje databáze: EXCLUDE constraint `no_overlapping_confirmed` nad `(station_id, tstzrange(start_time, end_time, '[)'))` pro řádky ve stavu CONFIRMED. Kontrola v service vrstvě zůstává kvůli srozumitelné chybě v běžném případě; porušení constraintu service převede na `OverlapError`. Stejné řešení převezme walking skeleton pro CP1, v C03 ho zdůvodní ADR. Souvisí s pressure R. |

### Ověření po změně (commit `6185d77`)

Prostředí: Windows 11, Python 3.12.8, PostgreSQL 16 (`postgres:16` v Dockeru), SQLAlchemy 2.1.6, psycopg 3.3.6, pytest 9.1.1.

```text
$ python -m pytest -v        (ve složce spike/)
tests/test_concurrency_risk.py::test_two_concurrent_confirmations_cannot_both_succeed PASSED [ 25%]
tests/test_db_constraint.py::test_database_rejects_overlapping_confirmed_rows_even_without_service PASSED [ 50%]
tests/test_db_constraint.py::test_database_allows_adjacent_confirmed_and_overlapping_drafts PASSED [ 75%]
tests/test_overlap.py::test_overlapping_confirmation_is_rejected_and_state_persists PASSED [100%]
============================== 4 passed in 0.30s ==============================
```

Kontrola, že testy pravidlo skutečně ověřují: v dočasné kopii `spike/` jsme kód záměrně pokazili a spustili stejné testy (repozitář beze změny).

| Úprava kódu | Výsledek | Co z toho plyne |
|---|---|---|
| bez EXCLUDE constraintu | 2 failed: `test_two_concurrent_confirmations…` (`assert 2 == 1`), `test_database_rejects_overlapping…` (`DID NOT RAISE IntegrityError`) | testy odhalí chybějící ochranu při souběhu i na úrovni DB |
| constraint s uzavřeným intervalem `'[]'` místo `'[)'` | 2 failed: `test_database_allows_adjacent…` a `test_overlapping_confirmation…` (`ExclusionViolation` u navazující rezervace) | testy odhalí příliš přísné pravidlo, které by porušilo BR-01 (navazující časy jsou povolené) |

### Nález po integraci: deadlock při současném zápisu

Po sloučení PR #4 test souběhu při opakovaném spouštění občas selhal: 3 z 50 běhů (`test_concurrency_risk.py`). Příčina: když oba zápisy CONFIRMED proběhnou v tentýž okamžik, čekají při kontrole EXCLUDE constraintu jeden na druhý a PostgreSQL jeden z nich ukončí chybou `DeadlockDetected` (ne porušením constraintu). Invariant platil i v těchto bězích (CONFIRMED zůstala jedna), ale prohraný požadavek dostal neošetřenou chybu databáze místo `OverlapError`.

| | Před opravou | Po opravě |
|---|---|---|
| `spike/tests/test_concurrency_risk.py`, 50 běhů | 47 passed, 3× `DeadlockDetected` | 50 passed |
| `src/tests/test_deadlock.py` (deadlock vyvolaný deterministicky) | 10 z 10 selhalo (`DeadlockDetected`) | 100 z 100 prošlo |

Oprava: po `DeadlockDetected` se zápis opakuje (nejvýše 3 pokusy s krátkou pauzou); opakovaný zápis už vidí výsledek druhé transakce a skončí `OverlapError` / `OVERLAP` (`spike/src/service.py`, `src/reservations/store.py`). Riziko je zapsané v ADR-01 mezi přijatými negativními důsledky.

## Evidence C02: specifikace → běžící aplikace

**Přijatá baseline:** Specification Baseline v0.2 (v0.1 schválena před změnou). Doména a pravidla z C01: firemní nabíjecí stanice, zaměstnanci, Facility admin, Notification Service.

**Předvedené základní operace:**

| Operace | Úspěšný příklad | Negativní nebo hraniční příklad |
|---|---|---|
| OP-01 Create | alice, AC-1 `[10:00, 11:00)` → DRAFT | `[10:00, 10:00)` → `INVALID_INTERVAL`; 4,5 h → `INVALID_DURATION`; `[07:00, 08:00)` → `START_IN_PAST` |
| OP-02 Check Availability | CONFIRMED `[10:00, 11:00)`, dotaz `[11:00, 12:00)` → AVAILABLE | dotaz `[10:30, 11:30)` → UNAVAILABLE; AC-2 → UNAVAILABLE |
| OP-03 Confirm | volný DRAFT → CONFIRMED a e-mail | překryv → `OVERLAP`, zůstává DRAFT; druhá v témže dni → `DAILY_LIMIT`; dvě souběžná → právě jedna CONFIRMED |
| OP-04 Cancel | CONFIRMED → CANCELLED, interval znovu AVAILABLE | v čase začátku → `TOO_LATE`; cizí rezervace → `UNAUTHORIZED` |
| OP-05 Approve / Reject | schválení → CONFIRMED; zamítnutí → REJECTED | schvaluje zaměstnanec → `UNAUTHORIZED`; rozhodnutí v čase začátku → `EXPIRED` |

**Skutečně provedené příklady ověření:**

- `python reservation.py test`: **40/40 příkladů prošlo** (výstup níže). Stejných 40 příkladů se stejnými názvy prochází i ve webové ukázce (`app/index.html`, část Automatické ověření).
- Mutační kontrola testů (`python tools/mutation_check.py`, kód se mění jen v dočasné kopii): po odebrání zámku selže test souběhu (`['CONFIRMED', 'CONFIRMED']`), po odebrání denního limitu selžou oba příklady `DAILY_LIMIT`, po uzavření intervalů (`<=` místo `<`) selžou tři hraniční příklady a po vypnutí kontroly provozu stanice selže příklad dostupnosti AC-2.
- `python reservation.py demo` (výstup níže) a připravené ukázky ve webové aplikaci.

<details>
<summary>Výstup <code>python reservation.py test</code></summary>

```text
Příklady ověření: Specification Baseline v0.2 (čas 2026-10-11 08:00 UTC)

OP-01 Create Reservation
  [PASS] platný požadavek -> DRAFT
  [PASS] dva DRAFTy na stejný čas -> vzniknou oba
  [PASS] začátek == konec -> INVALID_INTERVAL
  [PASS] přesně 4 hodiny -> DRAFT
  [PASS] 4,5 hodiny -> INVALID_DURATION
  [PASS] začátek v minulosti -> START_IN_PAST
  [PASS] neznámá stanice -> UNKNOWN_STATION
  [PASS] Facility admin rezervaci nevytváří -> UNAUTHORIZED

OP-02 Check Availability (CONFIRMED [10:00, 11:00))
  [PASS] dotaz [09:00, 10:00) -> AVAILABLE
  [PASS] dotaz [10:30, 11:30) -> UNAVAILABLE
  [PASS] dotaz [11:00, 12:00) -> AVAILABLE
  [PASS] DRAFT stanici neblokuje -> AVAILABLE
  [PASS] stanice mimo provoz -> UNAVAILABLE

OP-03 Confirm Reservation
  [PASS] volný DRAFT -> CONFIRMED + e-mail
  [PASS] překryv s potvrzenou -> OVERLAP, zůstává DRAFT
  [PASS] navazující [11:00, 13:00) -> CONFIRMED
  [PASS] druhá potvrzená v témže dni -> DAILY_LIMIT
  [PASS] další den -> CONFIRMED
  [PASS] stanice mimo provoz -> INACTIVE_STATION
  [PASS] cizí rezervace -> UNAUTHORIZED
  [PASS] už potvrzená -> INVALID_STATE
  [PASS] po začátku rezervace -> TOO_LATE
  [PASS] dvě souběžná potvrzení -> právě jedno CONFIRMED

OP-04 Cancel Reservation
  [PASS] DRAFT před začátkem -> CANCELLED
  [PASS] CONFIRMED -> CANCELLED, stanice volná, e-mail
  [PASS] v okamžiku začátku -> TOO_LATE, zůstává CONFIRMED
  [PASS] opakované zrušení -> úspěch beze změny
  [PASS] cizí rezervace zaměstnancem -> UNAUTHORIZED
  [PASS] Facility admin zruší cizí rezervaci -> CANCELLED

REQ-09 Notifikace
  [PASS] Notification Service nedostupná -> CONFIRMED, e-mail FAILED

v0.2 OP-05 Approve / Reject Reservation
  [PASS] Confirm na DC-1 -> PENDING_APPROVAL, bez e-mailu
  [PASS] PENDING_APPROVAL stanici neblokuje -> AVAILABLE
  [PASS] schválení -> CONFIRMED + e-mail
  [PASS] schvaluje zaměstnanec -> UNAUTHORIZED
  [PASS] zamítnutí -> REJECTED + e-mail
  [PASS] mezitím potvrzený překryv -> OVERLAP, zůstává PENDING
  [PASS] denní limit při schválení -> DAILY_LIMIT
  [PASS] zpožděné schválení v 09:59 -> CONFIRMED
  [PASS] rozhodnutí v 10:00 (začátek) -> EXPIRED
  [PASS] zrušení PENDING_APPROVAL -> CANCELLED

40/40 příkladů prošlo.
```

</details>

<details>
<summary>Výstup <code>python reservation.py demo</code></summary>

```text
Ukázka C02 · simulovaný čas 2026-10-11 08:00 UTC
Stanice: AC-1 (AC 22 kW), DC-1 (DC 50 kW, schvaluje Facility admin), AC-2 (mimo provoz)

  [OK]         alice vytvoří AC-1 10:00-11:00 -> R0001 DRAFT
  [OK]         dostupnost AC-1 10:00-11:00 -> AVAILABLE
  [OK]         alice potvrdí R0001 -> R0001 CONFIRMED
  [OK]         dostupnost AC-1 10:30-11:30 -> UNAVAILABLE
  [OK]         bob vytvoří AC-1 10:30-11:30 -> R0002 DRAFT
  [ODMÍTNUTO]  bob potvrdí R0002 -> OVERLAP (R0001): Stanice je v tomto čase obsazená potvrzenou rezervací (BR-02).
  [OK]         bob vytvoří DC-1 12:00-13:00 -> R0003 DRAFT
  [OK]         bob potvrdí R0003 -> R0003 PENDING_APPROVAL
  [ODMÍTNUTO]  alice schválí R0003 -> UNAUTHORIZED: Schvalovat a zamítat může jen Facility admin.
  [OK]         admin schválí R0003 -> R0003 CONFIRMED
  [OK]         alice zruší R0001 -> R0001 CANCELLED
  [OK]         dostupnost AC-1 10:30-11:30 -> AVAILABLE

E-maily (Notification Service):
  SENT   alice@example.com  Rezervace R0001 je potvrzená
  SENT   bob@example.com    Rezervace R0003 je potvrzená
  SENT   alice@example.com  Rezervace R0001 je zrušená
```

</details>

**Nalezený nesoulad a způsob vyřešení:**

| # | Nesoulad | Kde byl problém | Řešení |
|---|---|---|---|
| 1 | První návrh od AI kontroloval kolizi už při Create. | implementace | Specifikace má přednost: Create kolizi neřeší, stejně jako v C01. Opraven kód, ne REQ-01. |
| 2 | Podklady C02 vygenerované pomocí AI popisovaly jinou doménu (rezervace studoven v knihovně) a tvrdily, že je to doména z C01. | specifikace | C02 je převedeno na doménu z C01: nabíjecí stanice, zaměstnanci, Facility admin, Notification Service. Struktura specifikace a logika schvalování zůstaly. |
| 3 | Pravidlo BR-04 tvrdilo „30 min až 4 h, z C01“, ale doménové pravidlo C01 je „nejvýše 4 h a jedna CONFIRMED za den“. | specifikace i implementace | BR-04 podle C01, do Confirm i Approve doplněn denní limit (`DAILY_LIMIT`), vymyšlené minimum 30 min odstraněno. |
| 4 | Check Availability hlásila stanici mimo provoz jako volnou, ale Confirm ji odmítl. | specifikace i implementace | REQ-02 doplněn o „stanice mimo provoz → UNAVAILABLE“, opraven kód, přidán příklad. |
| 5 | Zvažované předběžné blokování stanice pro PENDING_APPROVAL by porušilo REQ-02. | specifikace | Tým rozhodl: PENDING_APPROVAL neblokuje, BR-02 se vyhodnocuje až při schválení. Opraveno ve specifikaci před úpravou kódu na v0.2. |
| 6 | Hranice „zrušit před začátkem“ nebyla přesná. | specifikace | Sjednoceno na `now < start_time` (čas rovný začátku je `TOO_LATE`) se stejnými hodinami ve specifikaci, testech i aplikaci. |

**Shrnutí dopadu změny:** Create, Check Availability, BR-01, BR-02 a BR-04 se nezměnily. Confirm se větví podle `requires_approval`. Facility admin dostal operaci Approve / Reject, přibyly stavy PENDING_APPROVAL, REJECTED a EXPIRED a Cancel umí zrušit i čekající žádost.

**Zbývající předpoklad / neznámá:** TBD-01 až TBD-06, viz `docs/specification.md`, část Rozhodnutí týmu a otevřené otázky.

**Architektonické drivery přenesené do C03:** D1 až D4 (popsané v `docs/specification.md`, část Dopad změny C02) a navíc:

5. **D5 Pravidla jsou napsaná dvakrát.** `reservation.py` a `app/index.html` obsahují stejnou doménu ve dvou jazycích a jejich shodu automaticky nic nehlídá; v C03 by webová ukázka měla volat jedno API místo vlastní kopie pravidel.

**Commit / tag aplikace:** commit `a4e1f4e`, tag `c02-baseline-v0.2`. Příkaz ověření: `python reservation.py test`.

## C03 — Architecture Evidence

Podrobnosti jsou v `docs/architecture-and-decisions.md`, části C03 A–L.

**Baseline:** Specification Baseline v0.2 (tag `c02-baseline-v0.2`).

**Part A:** AS-IS trace scénáře OP-03 Confirm v `reservation.py`; šest nálezů (souběh jen v jednom procesu, e-mail pod zámkem, neošetřená chyba služby, stav jen v paměti, pravidla podruhé v JavaScriptu, neověřená identita).

**Drivers:** DR1 souběh (BR-02, BR-04), DR2 trvalý stav, DR3 selhání notifikace, DR4 čas (vypršení žádosti).

**Decision question:** Kde se musí udělat autoritativní rozhodnutí o přechodu do CONFIRMED, aby BR-02 a BR-04 platily i při souběžných požadavcích a ve více procesech?

**Alternatives:** A: aplikace v transakci zamkne řádky stanice a uživatele (`SELECT … FOR UPDATE`); B: invarianty ve schématu PostgreSQL (EXCLUDE constraint, unikátní částečný index).

**Scenario walkthrough:** dvě souběžná konfliktní potvrzení téže stanice a varianta jednoho uživatele na dvou stanicích ve stejný den; obě alternativy dají právě jednu CONFIRMED, liší se tím, co se stane při opomenutí v kódu.

**ADR:** ADR-01, alternativa B, přijato celým týmem. Unikátní index pro BR-04 ověřen v PostgreSQL 16 před rozhodnutím.

**Views:**

- domain class: `docs/diagrams/c03-domain-model.svg`
- context: `docs/diagrams/c03-context.svg`
- static architecture: `docs/diagrams/c03-components.svg`
- state ownership: tabulka G3
- runtime/deployment: `docs/diagrams/c03-deployment.svg`
- design sequence: `docs/diagrams/c03-sequence-confirm.svg`
- focused design class: `docs/diagrams/c03-design-classes.svg`

**Cross-view issues found/resolved:** (1) ADR-01 tvrdil, že Check Availability používá celou `AllocationPolicy` včetně BR-04, což odporuje REQ-02 → ADR upřesněn; (2) záznam SENT / FAILED neměl v H2 vlastníka → doplněna třída `NotificationIntegration`. Oba opraveny v artefaktech před změnou kódu.

**AS-IS → TO-BE delta:** 6× CHANGE (HTTP vstup, PostgreSQL místo paměti, kontrakt úložiště, constrainty místo `threading.Lock`, převod porušení constraintu, struktura service), 4× KEEP (AllocationPolicy, líné vypršení, chování notifikací, zmrazené artefakty C02), 2× VERIFY (e-mail až po COMMIT, databáze jen v úložišti).

**Implementation changes:** walking skeleton `src/` (FastAPI + SQLAlchemy + PostgreSQL), pět modulů podle G2, závislosti připnuté na verze starší dvou týdnů (`src/requirements.txt`). Po implementaci nalezen a opraven deadlock při současném zápisu (viz evidence C01, nález po integraci).

**Behaviour verification:** `cd src && python -m pytest` → 66 passed, z toho 54 testů C03: walking skeleton (2), 40 příkladů ověření C02 přes HTTP se shodnými názvy, souběh BR-02 a BR-04, invarianty v DB (4), deadlock (1), notifikace (2), architektura (4). U testů souběhu, invariantů, deadlocku a notifikací ověřeno, že při odebrané ochraně selžou. Skutečný server:

```text
$ uvicorn reservations.main:app        (DATABASE_URL = PostgreSQL ze spike C01)
POST /reservations             -> 201 {'id': 1, 'state': 'DRAFT'}
POST /reservations/1/confirm   -> 200 {... 'state': 'CONFIRMED' ...}
POST /reservations/2/confirm   -> 409 {'code': 'OVERLAP', ..., 'related': [1]}
```

**Architecture conformance rule + result:** databázi zná jen Reservation Store, HTTP jen Reservation API, závislosti podle G2, stav rezervace mění jen Reservation Management; `src/tests/test_architecture.py` 4 passed; při úmyslném porušení dva testy selžou se jménem souboru a řádkem.

**Remaining uncertainty / risk:**

- identita uživatele je jen hlavička `X-User-Id` (TBD-01);
- log notifikací je v paměti procesu a nedoručený e-mail se znovu neposílá (TBD-02);
- vypršení žádosti je líné, e-mail o vypršení by potřeboval plánovač (DR4);
- schéma vytváří aplikace při startu, nástroj na migrace chybí;
- webová ukázka `app/index.html` zůstává kopií pravidel C02 (driver D5), produktem je `src/`.

**Commit/tag:** walking skeleton `bb299e5`, oprava deadlocku `eb8c636`; celý stav C03 označuje tag `c03-architecture`.

## C04

C04 nemělo samostatné zadání: cvičení 3 a 4 byla věnována rozsáhlému zadání C03. Tým proto nevybíral quality concern ani nedělal měření (Quality Concern → Evaluable Criterion → Measurement → Decision); v C06 jsou položky Q1–Q3 pro tento projekt N/A.

## C05 DD Verification Evidence

DD popisuje jednotku přidělení stanice ve walking skeletonu `src/` (po C03). První verze DD byla ověřena 13 testy nad aplikací C02 (`tests/test_allocation.py`); ty zůstávají a dál procházejí. Testy níže ověřují aktuální DD.

**Tests derived from DD:**

| DD element / decision | What must hold? | Test level | Test case |
|---|---|---|---|
| kontrakt `AllocationPolicy.check()` | volný slot → `allow()`, vstupy se nezmění | unit | `src/tests/test_allocation_dd.py::test_free_slot_is_allowed_and_inputs_are_not_changed` |
| algoritmus: BR-01 hranice | navazující intervaly nejsou překryv | unit | `test_adjacent_interval_is_not_an_overlap` |
| algoritmus: BR-02 | OVERLAP vrací id všech konfliktních | unit | `test_overlap_returns_code_and_all_conflicting_ids` |
| algoritmus: jen CONFIRMED blokuje | DRAFT, PENDING, CANCELLED, REJECTED, EXPIRED neblokují | unit | `test_only_confirmed_reservations_block` |
| algoritmus: BR-04 a UTC den | 23:30 UTC a 00:30 UTC dalšího dne jsou různé dny | unit | `test_daily_limit_uses_utc_date_of_start` |
| decision table: pořadí pravidel | INACTIVE_STATION před OVERLAP před DAILY_LIMIT | unit | `test_check_order_inactive_then_overlap_then_daily_limit` |
| kontrakt `relevant_for()` | jen CONFIRMED téže stanice nebo téhož uživatele, bez kandidáta | component (PostgreSQL) | `test_relevant_for_returns_confirmed_of_same_station_or_user_only` |
| kontrakt `save()`: porušení invariantu | `AllocationConflict(OVERLAP, related)`, stav v DB beze změny | component (PostgreSQL) | `test_save_reports_violated_invariant_as_allocation_conflict` |
| kontrakt `save()`: deadlock | opakovaný zápis → `OVERLAP`, ne chyba databáze | component (PostgreSQL) | `src/tests/test_deadlock.py` |
| state transition | DRAFT → CONFIRMED, právě jeden e-mail | component | `test_state_transition_draft_to_confirmed_and_one_mail` |
| failure behavior: zamítnutá alokace | stav DRAFT, žádný e-mail | component | `test_rejected_allocation_leaves_reservation_draft_and_sends_nothing` |
| collaboration: e-mail po COMMIT | během pomalého odeslání nedrží potvrzení transakci; v okamžiku odeslání je CONFIRMED zapsaná | component | `test_slow_notification_does_not_delay_conflicting_confirmation`, `test_notifications.py::test_email_is_sent_only_after_state_is_committed` |
| failure behavior Notifieru | jakákoli výjimka služby → CONFIRMED, FAILED, volající chybu nedostane | component | `test_notifications.py::test_unexpected_notification_error_does_not_reach_caller` |
| concurrency REQ-04 | dvě souběžná konfliktní potvrzení → právě jedno CONFIRMED (BR-02 i BR-04) | integration (HTTP + PostgreSQL) | `test_op03_concurrent_confirmations`, `test_concurrency.py` |
| collaboration: jedno místo pravidla | Confirm i Approve volají stejnou policy | component | `test_approve_uses_the_same_policy` |

**Zdůvodnění úrovně u vybraných testů:**

- `test_check_order_inactive_then_overlap_then_daily_limit`
  - Selected level: unit.
  - Why this level: `AllocationPolicy` je čistá funkce, vstupy se sestaví přímo, bez databáze a HTTP.
  - What design decision does this test verify? Pořadí kontrol je součástí kontraktu: volající dostane vždy první porušené pravidlo.
- `test_save_reports_violated_invariant_as_allocation_conflict`
  - Selected level: component se skutečným PostgreSQL.
  - Why this level: invariant je ve schématu databáze (ADR-01), náhradní úložiště v paměti by ho nemělo, test by ověřoval jen sám sebe.
  - What design decision does this test verify? Úložiště převede porušení constraintu na stejnou doménovou chybu, jakou vrací policy, a stav nezmění.
- `test_slow_notification_does_not_delay_conflicting_confirmation`
  - Selected level: component (service + PostgreSQL + Notifier, dvě vlákna).
  - Why this level: ověřuje pořadí kroků v čase mezi dvěma operacemi; na úrovni jedné třídy ho vidět nelze.
  - What design decision does this test verify? E-mail se odesílá až po `COMMIT`: konfliktní potvrzení během pomalého e-mailu dostane `OVERLAP` hned (< 0,3 s), nečeká na transakci.

**Unit/component tests executed:**

```text
$ cd src && python -m pytest tests/test_allocation_dd.py
12 passed

$ cd src && python -m pytest
66 passed

$ python -m unittest discover -s tests          (první verze DD, aplikace C02)
Ran 13 tests ... OK

$ python tools/mutation_check.py
7/7 mutací zabito.
```

Kontrola, že testy rozhodnutí DD opravdu hlídají (dočasná kopie `src/`, repozitář beze změny): e-mail odeslaný před zápisem → selžou `test_slow_notification_…` a `test_email_is_sent_only_after_state_is_committed`; bez opakování po deadlocku → `test_deadlock.py` selže 10 z 10; bez constraintů z ADR-01 → selžou testy souběhu.

**Design ↔ implementation mismatch:**

| DD decision | Implemented? | Evidence | Action |
|---|---|---|---|
| `AllocationPolicy` jako čistá funkce s pevným pořadím pravidel | YES | `src/reservations/domain.py`; 6 unit testů | keep |
| Confirm i Approve rozhoduje stejná policy přes `_allocate()` | YES | `src/reservations/service.py`; `test_approve_uses_the_same_policy` | keep |
| service závisí jen na kontraktech `ReservationRepository` a `Notifier` | YES | `src/tests/test_architecture.py` | keep |
| `save()` převede porušení invariantu na `AllocationConflict` se stejnými kódy | YES | `SqlReservationRepository._translate()`; `test_save_reports_…` | keep |
| `save()` po deadlocku opakuje zápis | YES, doplněno po nálezu | `SqlReservationRepository.save()`; `test_deadlock.py` | update DD i kód (provedeno) |
| e-mail až po `COMMIT`, jakákoli chyba → FAILED | YES | `_allocate()`, `NotificationIntegration`; 3 testy | keep |
| kontrakt `ReservationRepository` v DD | PARTLY, záměrně | kód má navíc `user()`, `add()`, `confirmed_for_station()`, `expire_pending()` pro ostatní operace | keep: DD popisuje jen část potřebnou pro přidělení |
| (první verze) souběh hlídá jeden zámek v procesu | nahrazeno | ADR-01 | vyřešeno v C03 |

**Resolution:** kód realizuje DD; jediná změna DD vznikla z nálezu (opakování po deadlocku) a je zapsaná v DD, v ADR-01 i v evidence C01. Rozdíl v šíři kontraktu úložiště je vědomý.

**Remaining design risk:**

- log notifikací je jen v paměti procesu a nedoručené e-maily se znovu neposílají (TBD-02);
- při velmi silném souběhu by tři pokusy po deadlocku nemusely stačit a volající by dostal chybu databáze (při testech nepozorováno);
- webová ukázka `app/index.html` je kopie pravidel C02 (driver D5).

**Commit/tag:** první verze DD `0686cde` (tag `c05-detailed-design`); aktualizace po C03 je součástí stavu označeného tagem `c03-architecture`.
