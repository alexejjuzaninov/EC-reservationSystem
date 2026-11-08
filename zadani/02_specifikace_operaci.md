# C02 · Specifikace rezervačních operací

**Baseline v0.1:** commit `6fa569b` potvrzoval rezervaci okamžitě. **Pracovní verze v0.2:** Flyway V22 zavádí návrh, žádost o schválení, rozhodnutí vlastníka a další koncové stavy. Změnu schvalování výslovně přijal zadavatel. [Stavový diagram](diagramy/08_stavy.png) a [aktivita](diagramy/09_aktivita.png) používají stejná pravidla BR-01 až BR-06 z [C01](01_zamer_a_pozadavky.md).

## Kontrakty

| Operace | Předpoklady | Výsledek / postpodmínka | Chybové případy |
|---|---|---|---|
| **O1 · Check Availability** `GET /api/stations/{id}/availability` | známá stanice, platný interval `startAt`–`endAt` | `available`, důvod, cena a provize; čtení nic nerezervuje | 400 interval; 404 stanice; obsazený čas vrací 200 + `available=false` |
| **O2 · Create Reservation** `POST /api/bookings` | řidič, publikovaná stanice, BR-02 | 201, uložený `DRAFT` se snapshotem ceny a stanice; bez platby | 400 vstup/vlastní stanice; 403 role; 409 neaktivní stanice |
| **O3 · Confirm Reservation** `POST /api/bookings/{id}/confirm` | řidič daného `DRAFT`; nová kontrola BR-02/03/04 | 200: `CONFIRMED` + `BOOKED`, nebo `PENDING_APPROVAL` + `REQUESTED` podle politiky stanice | 403 cizí aktér; 409 obsazený slot či neplatný přechod |
| **O4 · Cancel Reservation** `POST /api/bookings/{id}/cancel` | řidič, vlastník nebo správce; před začátkem | 200, `CANCELLED`; potvrzený slot se uvolní, simulovaná platba se stornuje | 403 cizí aktér; 409 uzavřený nebo proběhlý termín |

**Rozšíření v0.2 · Decide Approval:** `POST /api/bookings/{id}/decision` s `{approve:boolean}` smí pouze vlastník stanice pro `PENDING_APPROVAL`. Schválení znovu kontroluje dostupnost a ukládá `CONFIRMED` + `BOOKED`; zamítnutí ukládá `REJECTED` bez platby. Obojí eviduje čas a aktéra. Cizí aktér dostane 403; druhé rozhodnutí či kolize 409. Pravidlo stanice nastavuje vlastník přes `PATCH /api/stations/{id}/booking-approval`.

`DRAFT` a `PENDING_APPROVAL` slot neblokují. Mezi kontrolou dostupnosti a potvrzením se proto může situace změnit; konečný přechod je transakční a chráněný databázovým omezením proti překryvu. Po začátku termínu nevyřízená žádost expiruje. Přístupový pokyn k soukromé stanici se řidiči zpřístupní až v `CONFIRMED`.

## Ověření specifikace

| Scénář | Očekávání | Pozorování |
|---|---|---|
| návrh → žádost | `DRAFT` → `PENDING_APPROVAL`, bez platby | splněno |
| cizí rozhodnutí | 403, stav beze změny | splněno |
| schválení a druhý řidič | první `CONFIRMED`, druhý konflikt 409 | splněno |
| zamítnutí | `REJECTED`, bez platby | splněno |
| zrušení | `CANCELLED`, slot znovu dostupný | splněno |
| souběžné schválení | právě jeden `CONFIRMED` | splněno pro ověřenou dvojici |

Výsledky a databázový oracle jsou shrnuty v [C05](05_detailni_navrh_a_testy.md) a zaznamenány v [důkazech](dukazy/). Formalizované týmové schválení verze v0.2 zatím není doloženo.
