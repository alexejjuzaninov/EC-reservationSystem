# C05 · Detailní návrh a ověření

**Jednotka:** `BookingService` v balíčku `booking`. [Komponenty](diagramy/06_komponenty.png), [sekvence](diagramy/07_sekvence.png) a [doménový model](diagramy/10_domena.png) zobrazují stejnou hranici odpovědnosti.

| Odpovědnost | Konkrétní mechanismus |
|---|---|
| vstup a oprávnění | `create`, `confirm`, `decide`, `cancel` kontrolují aktéra a stav |
| interval a dostupnost | BR-02/03, týdenní hodiny, blokace a kolize |
| změna stavu | transakční přechod `DRAFT` / `PENDING_APPROVAL` / `CONFIRMED` |
| souběh | zámek rozvrhu stanice + GiST exclusion v DB |
| události | zápis do `reservation.outbox` v transakci |
| expirace | ukončení nevyřízené žádosti po začátku termínu |

## Kontrakty a rozhodovací logika

`create(actor, stationId, startAt, endAt)` vrací `DRAFT` jen řidiči s platným budoucím intervalem. `confirm(id, actor)` znovu ověří dostupnost: bez politiky schvalování vrací `CONFIRMED`, jinak `PENDING_APPROVAL`. `decide(id, owner, approve)` vyžaduje vlastníka a čekající žádost; zamítnutí vrací `REJECTED`, schválení po nové kontrole vrací `CONFIRMED`. `cancel(id, actor)` před začátkem uvolní termín a je idempotentní pro již zrušený stav. Chybný vstup → 400, cizí aktér → 403, neznámé ID → 404, neplatný přechod nebo kolize → 409.

**Algoritmus kolize:** pro stejnou stanici blokuje pouze `CONFIRMED`; intervaly se překrývají právě když `existing.start < requested.end` a `requested.start < existing.end`. Navazující intervaly se tedy mohou rezervovat. Předběžný výsledek dostupnosti není závazný; při zápisu rozhoduje DB constraint nad polootevřeným intervalem `[start,end)`.

**Schválení v transakci:**

1. Ověř vlastníka, zamkni rozvrh stanice a žádost.
2. Vyžaduj `PENDING_APPROVAL`; po začátku ulož `EXPIRED`.
3. Při zamítnutí ulož `REJECTED`, čas, aktéra a událost.
4. Při schválení znovu ověř stanici, hodiny, blokace a kolize. Ulož `CONFIRMED` + `BOOKED`; GiST omezení chrání i souběžné pokusy.
5. Z `BOOKED` vznikne idempotentně simulovaná platba a oznámení. `REQUESTED` ani `REJECTED` platbu nespouští.

## Odvozené testy

| ID · hranice | Očekávaný oracle | Pozorování |
|---|---|---|
| T1 · návrh | 201; DB `DRAFT`; bez platby | PASS |
| T2 · žádost | 200; `PENDING_APPROVAL`; pouze `REQUESTED` | PASS |
| T3 · cizí aktér | 403; stav beze změny | PASS |
| T4 · schválení | 200; `CONFIRMED`; událost `BOOKED` | PASS |
| T5 · opakované rozhodnutí | 409 | PASS |
| T6 · stejný slot | druhé potvrzení 409; jen jeden obsazený slot | PASS |
| T7 · zamítnutí / zrušení | `REJECTED` bez platby; `CANCELLED` uvolní slot | PASS |
| T8 · paralelní schválení | odpovědi 200/409; jeden `CONFIRMED` v DB | PASS |
| T9 · expirace | `EXPIRED` + událost; bez platby | PASS |

Provedené průchody: [rezervace](dukazy/overeni_rezervaci.txt), [paralelní rozhodnutí](dukazy/overeni_paralelniho_schvaleni.txt), [souběh a expirace](dukazy/overeni_soubehu_a_expirace.txt), [politika stanice](dukazy/overeni_politiky_stanice.txt). Oracle je nezávislý SQL dotaz nad stavem rezervace, outboxu a plateb, nikoli porovnání se současným výstupem metody. Testy používají izolované vzorové termíny; jednorázově ověřená paralelní dvojice není zátěžový test.

**Úroveň ověření:** T1–T9 jsou integrační průchody přes HTTP a PostgreSQL. T8 ověřuje databázový invariant při dvou souběžných spojeních.

Reprodukce: spustit aplikaci a `python verification/overeni_rezervaci.py`; další scénáře jsou ve složce `verification/`. Testovací skripty vytvářejí označené vzorové záznamy.
