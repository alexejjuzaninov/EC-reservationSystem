# C01 · Záměr a požadavky

**Tým:** SW-DEV-AJVZMPIA — Viacheslav Zlobin, Maksym Panfilov, Aleksej Južaninov, Ivan Akulovich. **Repozitář:** [EC-reservationSystem](https://github.com/alexejjuzaninov/EC-reservationSystem).

## Doména a hranice

EC provozuje vlastní nabíjecí stanice a zprostředkovává nabíjení na stanicích firem a soukromých vlastníků. Řidič vyhledá místo v Česku nebo USA, zvolí čas a podá rezervaci. Vlastník rozhoduje o žádostech tam, kde vyžaduje předchozí souhlas. Z potvrzené partnerské rezervace připadá EC provize **12 %**.

Prototyp obsahuje mapu s přibližně 141 tisíci vzorovými lokalitami, role, správu stanic, rezervace, oznámení, přehledy a simulovaný platební náhled. Reálné stržení platby, OCPP telemetrie a produkční přihlášení jsou mimo rozsah.

| Aktér | Hlavní cíl |
|---|---|
| Řidič | najít místo, ověřit termín, rezervovat, sledovat stav a zrušit žádost |
| Soukromý vlastník | nabídnout stanici, nastavit dostupnost a schvalovat žádosti |
| Firma | spravovat více vlastních stanic a jejich rezervace |
| Operátor EC | sledovat provoz vlastních stanic |
| Správce | moderovat publikaci stanic a kontrolovat síť |

## Project Frame

| Položka | Rozhodnutí pro EC Reservation |
|---|---|
| Resource | Nabíjecí stanice s polohou, konektorem, výkonem, cenou, vlastníkem a rozvrhem. |
| Reservation a User | Rezervace má ID, řidiče, stanici, časový interval, stav a cenu; uživatel má roli určující oprávnění. |
| Základní operace | Zkontrolovat dostupnost, vytvořit návrh, potvrdit nebo požádat o schválení, rozhodnout o žádosti, zrušit rezervaci. Kontrakty jsou v [C02](02_specifikace_operaci.md). |
| Trvalý stav | Uživatelé; stanice a rozvrhy; rezervace; události outboxu a simulované platby. |
| Stavy rezervace | `DRAFT` → `CONFIRMED` → `CANCELLED`; u vybraných stanic `DRAFT` → `PENDING_APPROVAL` → `CONFIRMED`, `REJECTED` nebo `EXPIRED`. |
| Měnící operace | `confirm(id)` znovu ověří termín. Podle politiky stanice uloží `CONFIRMED`, nebo `PENDING_APPROVAL`; pouze první stav obsadí slot. |
| Společné pravidlo | Dvě potvrzené rezervace téže stanice se nesmějí časově překrývat. |
| Vlastní pravidlo domény | U stanice vyžadující schválení smí žádost potvrdit jen její vlastník; EC získává 12 % z potvrzené partnerské rezervace. |
| Hranice systému | Platební poskytovatel a telemetrie stanice jsou externí oblasti; prototyp místo nich používá jasně označené simulace. Oznámení vznikají z událostí outboxu. |
| Předpoklad | Vlastník udržuje otevírací dobu a blokace aktuální; prototyp neověřuje fyzický stav konektoru v okamžiku příjezdu. |
| Neznámá v C01 | Co se stane, pokud vlastník nerozhodne před začátkem termínu? V C02 rozhodnuto: žádost přejde do `EXPIRED`, bez platby. |

## Přijatá pravidla

| ID | Pravidlo |
|---|---|
| BR-01 | Rezervaci vytváří řidič; vlastník nesmí rezervovat vlastní stanici. |
| BR-02 | Termín začíná v budoucnu a trvá 30–240 minut. |
| BR-03 | Stanice je aktivní a zveřejněná; termín respektuje otevírací dobu a blokace. |
| BR-04 | Dvě potvrzené rezervace stejné stanice se nesmějí časově překrývat. |
| BR-05 | U stanice se schvalováním rozhoduje jen její vlastník před začátkem termínu. |
| BR-06 | Platební simulace vzniká až po potvrzení; čekání a zamítnutí ji nevytváří. |

## Vybraný budoucí tlak a technický spike

**R · vyšší důsledky chyby:** při placeném nabíjení by dvojí rezervace znamenala cestu k obsazené stanici, reklamaci a ztrátu důvěry. Proto musí BR-04 platit i při souběžných rozhodnutích, nejen při kontrole ve webu.

**Otázka spike:** mohou dvě současná schválení překrývajících se žádostí vytvořit dvě `CONFIRMED` rezervace? Dvě čekající žádosti byly rozhodnuty souběžně přes HTTP; výsledky byly **200/409** a nezávislý dotaz do databáze našel právě **jednu** potvrzenou rezervaci. [Záznam](dukazy/overeni_paralelniho_schvaleni.txt) a [opakovatelný scénář](../verification/overeni_paralelniho_schvaleni.py) dokládají provedení. Rozhodnutí: konečný přechod chrání transakce a PostgreSQL GiST exclusion constraint; pouhé předběžné čtení dostupnosti nestačí. Jde o ověřenou dvojici, nikoli o zátěžový test.

## Technické rozhodnutí a průchozí kostra

**Stack:** Java 21, Spring Boot, PostgreSQL/PostGIS, Flyway a Redis. Spring Boot pokrývá HTTP vrstvu a transakční doménovou logiku; PostgreSQL drží závazný stav a vynucuje nepřekryv. Cena volby je složitější lokální běh než u aplikace bez databáze. Cílové mikroservisy jsou popsány v [C03](03_architektura_a_rozhodnuti.md); nynější prototyp je modulární aplikace.

**Walking skeleton:** `POST /api/bookings` → validace vstupu → `BookingService.create` → zápis `DRAFT` do PostgreSQL → HTTP 201 s ID → kontrola uloženého stavu. Tato cesta je implementovaná; [ověření rezervací](dukazy/overeni_rezervaci.txt) kontroluje HTTP odpověď i databázi. Rozšíření o schválení v C02 navazuje na stejný základ.

**Řízená změna:** schvalování vybraných rezervací je implementované ve V22; [C08](08_rizena_zmena_a_predani.md) popisuje rozhodnutí, dopady a testovací procedury.
