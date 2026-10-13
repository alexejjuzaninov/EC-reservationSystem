# Evidence and Evolution

## C01 Engineering Spike

Kód spike je ve složce `spike/`, postup spuštění je v `README.md`, část Rychlý start.

| Položka | Obsah |
|---|---|
| Question / unknown | Udrží kontrola překryvu v service vrstvě pravidlo BR-02 (potvrzené rezervace téže stanice se nepřekrývají), i když dvě potvrzení proběhnou souběžně? |
| What we did | PostgreSQL 16 v Dockeru, entity v SQLAlchemy a service vrstva s kontrolou překryvu. `test_overlap.py` ověří sekvenční případ a perzistenci po novém načtení v jiné session. `test_concurrency_risk.py` pustí dvě potvrzení překrývajících se rezervací ve dvou vláknech a bariérou zajistí, že obě dokončí kontrolu překryvu dřív, než kterékoli zapíše. Spuštěno přes pytest. |
| Observed result | Sekvenčně: překryv odmítnut, navazující rezervace potvrzena, stav po novém načtení trvá. Souběžně: obě rezervace skončí CONFIRMED (`AssertionError: assert 2 == 1`). Kontrola v aplikaci pravidlo při souběhu neudrží, protože databáze sama žádné omezení nemá. |
| Decision / what changes | BR-02 vynucuje databáze: EXCLUDE constraint `no_overlapping_confirmed` nad `(station_id, tstzrange(start_time, end_time, '[)'))` pro řádky ve stavu CONFIRMED. Kontrola v service vrstvě zůstává kvůli srozumitelné chybě v běžném případě; porušení constraintu service převede na `OverlapError`. Stejné řešení převezme walking skeleton pro CP1, v C03 ho zdůvodní ADR. Souvisí s pressure R. |

### Ověření po změně (commit `238e8ce`)

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

**Commit / tag aplikace:** commit `af2723f`, tag `c02-baseline-v0.2`. Příkaz ověření: `python reservation.py test`.

## C05 DD Verification Evidence

**Tests derived from DD** (`tests/test_allocation.py`, 13 testů):

| DD element / decision | What must hold? | Test level | Test case |
|---|---|---|---|
| kontrakt `AllocationPolicy.check()` | volný slot → `allow()`, vstupy se nezmění | unit | `test_free_slot_is_allowed_and_inputs_are_not_changed` |
| algoritmus: BR-01 hranice | navazující intervaly nejsou překryv | unit | `test_adjacent_interval_is_not_an_overlap` |
| algoritmus: BR-02 | OVERLAP vrací id všech konfliktních | unit | `test_overlap_returns_code_and_all_conflicting_ids` |
| algoritmus: jen CONFIRMED blokuje | DRAFT, PENDING, CANCELLED, REJECTED, EXPIRED neblokují | unit | `test_only_confirmed_reservations_block` |
| algoritmus: BR-04 a UTC den | 23:30 UTC a 00:30 UTC dalšího dne jsou různé dny | unit | `test_daily_limit_uses_utc_date_of_start` |
| decision table: pořadí pravidel | INACTIVE_STATION před OVERLAP před DAILY_LIMIT | unit | `test_check_order_inactive_then_overlap_then_daily_limit` |
| kontrakt `ReservationRepository.relevant_for()` | jen CONFIRMED téže stanice nebo téhož uživatele, bez kandidáta | unit | `test_relevant_for_returns_confirmed_of_same_station_or_user_only` |
| state transition | DRAFT → CONFIRMED, právě jeden e-mail | component | `test_state_transition_draft_to_confirmed_and_mail_queued_once` |
| failure behavior | zamítnutá alokace: stav DRAFT, žádný e-mail | component | `test_rejected_allocation_leaves_reservation_draft_and_sends_nothing` |
| failure behavior Notifier | libovolná výjimka z `send()` → CONFIRMED, FAILED, volající chybu nedostane | component | `test_unexpected_notifier_error_does_not_reach_caller` |
| collaboration: e-mail mimo zámek | pomalý `send()` neblokuje jinou operaci (< 0,3 s) | component | `test_slow_notifier_does_not_block_other_operations` |
| concurrency REQ-04 | dvě souběžná konfliktní potvrzení → právě jedno CONFIRMED | component | `test_concurrent_conflicting_confirmations_allow_exactly_one` |
| collaboration: jedno místo pravidla | Confirm i Approve volají stejnou policy | component | `test_approve_uses_the_same_policy` |

**Zdůvodnění úrovně u vybraných testů:**

- `test_check_order_inactive_then_overlap_then_daily_limit`
  - Selected level: unit.
  - Why this level: `AllocationPolicy` je čistá funkce, takže stačí sestavit vstupy přímo, bez systému, hodin a zámku.
  - What design decision does this test verify? Pořadí kontrol je součástí kontraktu: volající dostane vždy první porušené pravidlo v pořadí INACTIVE_STATION → OVERLAP → DAILY_LIMIT.
- `test_slow_notifier_does_not_block_other_operations`
  - Selected level: component (systém + zámek + Notifier, dvě vlákna).
  - Why this level: ověřuje spolupráci prvků v čase; na úrovni jedné třídy ho vidět nelze.
  - What design decision does this test verify? E-mail se připraví pod zámkem, ale odešle až po jeho uvolnění (oprava nálezu 2 z C03).
- `test_unexpected_notifier_error_does_not_reach_caller`
  - Selected level: component s náhradním `Notifier`.
  - Why this level: chybu externí služby simuluje dosazená implementace rozhraní.
  - What design decision does this test verify? REQ-09: jakákoli chyba služby se zapíše jako FAILED a výsledek operace nemění (oprava nálezu 3 z C03).

**Unit/component tests executed:**

```text
$ python -m unittest discover -s tests -v
...
Ran 13 tests in 1.06s
OK

$ python reservation.py test
40/40 příkladů prošlo.
```

Mutační kontrola testů (`python tools/mutation_check.py`): e-mail odeslaný pod zámkem → selže `test_slow_notifier…`; zachycení jen `NotificationUnavailable` → selže `test_unexpected_notifier…`; přesunutí kontroly provozu stanice za BR-04 → selže `test_check_order…`. Skript ověří i mutace z C02 a skončí chybou, pokud kontrolní běh neprojde nebo některou mutaci testy neodhalí. Výsledek: 7/7 mutací zabito.

**Design ↔ implementation mismatch:**

| DD decision | Implemented? | Evidence | Action |
|---|---|---|---|
| `AllocationPolicy` jako čistá funkce s pevným pořadím pravidel | YES | `reservation.py` `AllocationPolicy.check()`; testy policy | keep |
| Confirm i Approve rozhoduje stejná policy | YES | `_check_allocation()`; `test_approve_uses_the_same_policy` | keep |
| systém závisí jen na kontraktu `ReservationRepository` | PARTLY, opraveno | první verze měla v konstruktoru typ `InMemoryReservationRepository` a vlastnost `reservations` četla přímo `repository.items` | update code: typ `ReservationRepository`, `reservations` jde přes `all()` |
| e-mail mimo zámek, jakákoli chyba → FAILED | YES | `_queue_notification()`, `_dispatch_notifications()`; dva component testy | keep |
| jeden zámek zajišťuje REQ-04 | PARTLY | platí jen uvnitř jednoho procesu | keep pro C05; v CP1 nahradit zárukou v DB (otázka A8 z C03) |
| jedno místo pravidla | PARTLY | `app/index.html` má vlastní kopii; jediná změna tam: zachycení jakékoli chyby e-mailu | keep, vedeno jako riziko (driver D5) |

**Resolution:** kód upraven tam, kde se odchýlil od návrhu (závislost na kontraktu repository). Odchylky, které návrh vědomě přijímá (zámek v procesu, kopie pravidel ve webu), zůstávají a jsou vedené jako riziko.

**Remaining design risk:**

- REQ-04 platí jen v jednom procesu; `SqlReservationRepository` potřebuje omezení v DB nebo zámek řádku stanice;
- e-mail se odesílá synchronně ve vlákně volajícího; volající na pomalou službu stále čeká, jen už neblokuje ostatní operace; skutečná fronta (outbox v DB) je úkol pro CP1;
- nedoručené e-maily se znovu neposílají (TBD-02).

**Commit/tag:** commit `7a6f1af`, tag `c05-detailed-design`.
