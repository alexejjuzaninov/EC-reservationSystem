# Evidence and Evolution

## C01 Engineering Spike

Kód spike je ve složce `spike/`, scénář a výstup pytest jsou v `README.md`, část Engineering spike.

| Položka | Obsah |
|---|---|
| Question / unknown | Dokáže datová vrstva spolehlivě vynutit pravidlo o nepřekrývajících se CONFIRMED rezervacích, nebo se dvě souběžná potvrzení mohou prosadit obě? |
| What we did | PostgreSQL v Dockeru, entity a service vrstva, test se dvěma překrývajícími se a jednou navazující rezervací a test souběhu se dvěma vlákny; spuštěno přes pytest |
| Observed result | sekvenčně: překryv odmítnut, navazující rezervace potvrzena, stav po novém načtení trvá (1 passed); souběžně: obě potvrzení projdou (`assert 2 == 1`, test označen xfail) |
| Decision / what changes | kontrolu v service vrstvě necháváme jako čitelnou validaci; aby pravidlo platilo i při souběhu, dostane CP1 záruku na úrovni databáze (EXCLUDE constraint nad `tstzrange`, nebo zámek stanice v transakci); návrh v C03; souvisí s pressure R |

## Evidence C02: specifikace → běžící aplikace

Shodné s částí Evidence C02 v `README.md`.

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
- Mutační kontrola testů: po odebrání zámku selže test souběhu (`['CONFIRMED', 'CONFIRMED']`), po odebrání denního limitu selžou oba testy `DAILY_LIMIT`, po uzavření intervalů (`<=` místo `<`) selžou tři hraniční příklady a po vypnutí kontroly provozu stanice selže příklad dostupnosti AC-2.
- Diferenciální test: 4000 náhodných posloupností (60 921 operací) proběhlo v `reservation.py` i ve webové ukázce se shodným výsledkem každé operace, shodným konečným stavem i shodnými e-maily (0 rozdílů). Ve všech 4000 konečných stavech platí BR-02 i denní limit z BR-04.
- `python reservation.py demo` (výstup níže) a připravené ukázky ve webové aplikaci, ověřené v prohlížeči Chromium.

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

**Zbývající předpoklad / neznámá:** TBD-01 až TBD-06, viz `README.md`, část Rozhodnutí týmu a otevřené otázky.

**Architektonické drivery přenesené do C03:** D1 až D4 (popsané v `README.md`, část Dopad změny C02) a navíc:

5. **D5 Pravidla jsou napsaná dvakrát.** `reservation.py` a `app/index.html` obsahují stejnou doménu ve dvou jazycích. Shodu dnes hlídá diferenciální test; v C03 by webová ukázka měla volat jedno API místo vlastní kopie pravidel.

**Commit / tag aplikace:** tag `c02-baseline-v0.2`, commit [DOPLNIT hash]. Příkaz ověření: `python reservation.py test`.
