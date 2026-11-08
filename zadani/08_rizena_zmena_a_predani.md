# C08 · Řízená změna a předání

## CR-01 · Schvalování rezervace vlastníkem

| Položka | Rozhodnutí |
|---|---|
| Podnět | Vlastník soukromé nebo firemní stanice potřebuje rozhodnout, kdo u něj může nabíjet. |
| Výchozí baseline | Git `6fa569b`, Java 21, schéma V21: `POST /api/bookings` vytvořil `DRAFT` a `POST /api/bookings/{id}/confirm` jej potvrzoval bez rozhodnutí vlastníka. |
| Přijaté pravidlo | BR-05 v [C01](01_zamer_a_pozadavky.md): u vybraných stanic rozhoduje vlastník před začátkem. |
| Po změně | pracovní verze v0.2 / V22: `DRAFT` → `PENDING_APPROVAL` → `CONFIRMED`, `REJECTED` nebo `EXPIRED`. |
| Disposition | **ACCEPT.** Zadavatel změnu výslovně schválil; implementace a lokální testy jsou dokončeny. |

**Varianty:** okamžitě potvrzovat vše (menší změna, nesplňuje potřebu); rozhodování v rezervační doméně (atomický stav a ochrana slotu); oddělená schvalovací služba (samostatné nasazení, složitější koordinace). Pro prototyp je zvolena druhá varianta. V cílové architektuře zůstává rozhodnutí v rezervační mikroservise, nikoli v nové službě schvalování.

## Dopady

| Oblast | Stav | Důvod a ověření |
|---|---|---|
| Specifikace a stav | CHANGE | nové přechody a BR-05; [C02](02_specifikace_operaci.md) a [stavový diagram](diagramy/08_stavy.png) |
| Rezervační kód | CHANGE | `BookingService.confirm/decide`, oprávnění, revalidace slotu |
| Data | CHANGE | V22: politika stanice, nové stavy, čas a aktér rozhodnutí |
| Oznámení a platby | CHECK | `REQUESTED`/`REJECTED` oznámí výsledek; platba jen po `BOOKED` |
| Web | CHANGE | řidič vidí čekání; vlastník může schválit/zamítnout |
| Mapa a clustery | NO IMPACT | prostorové hledání stanic nepracuje se stavem rezervace |
| Regrese | CHECK | konflikt, zrušení, expirace a souběh mají nezávislý DB oracle |

## Testovací procedury

**TC-01 · Schválení a konflikt — PASS.** Základ: BR-04/05, baseline v0.2/V22. Data: stanice Ilyi `20000000-0000-0000-0000-000000000002`, Anna a Mark; referenční běh použil interval **12. 1. 2027 12:00–13:00 UTC**, skript při opakování najde volný budoucí termín. 1. Anna vytvoří návrh: očekává se 201 + DB `DRAFT`; pozorováno 201 + `DRAFT`. 2. Potvrdí: očekává se `PENDING_APPROVAL` bez platby; pozorováno. 3. Mark zkusí rozhodnout: očekává se 403 a stav beze změny; pozorováno. 4. Ilya schválí: očekává se `CONFIRMED` + `BOOKED`; pozorováno. 5. Mark potvrdí stejný slot: očekává se 409 a nejvýše jeden potvrzený slot; pozorováno. Oracle: přímé čtení `reservation.bookings`, `reservation.outbox` a `billing.simulated_charges`. [Záznam](dukazy/overeni_rezervaci.txt).

**TC-02 · Zrušení a zamítnutí — PASS.** Základ: BR-04/05/06, stejné účty, stanice a interval po TC-01. 1. Anna zruší rezervaci: očekává se `CANCELLED`, uvolnění slotu a storno simulované platby; pozorováno. 2. Mark potvrdí nový návrh: očekává se `PENDING_APPROVAL`; pozorováno. 3. Ilya zamítne: očekává se `REJECTED` bez Markovy platby; pozorováno. Oracle: DB stav rezervací a plateb nezávisle na odpovědi API. [Záznam](dukazy/overeni_rezervaci.txt).

## Předání

Verze V22 obsahuje schvalování rezervací, záznam rozhodnutí a navazující události. [TC-01/02](dukazy/overeni_rezervaci.txt) ověřují schválení, konflikt, zrušení a zamítnutí v databázi. Pro komerční provoz zbývá skutečná identita, platby, telemetrie a zátěžové ověření.
