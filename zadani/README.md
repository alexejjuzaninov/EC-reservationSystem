# EC Reservation · podklady SWI

**Tým SW-DEV-AJVZMPIA:** Viacheslav Zlobin, Maksym Panfilov, Aleksej Južaninov, Ivan Akulovich.  
**Projekt:** rezervační systém pro nabíjecí stanice provozované EC, firmami a soukromými vlastníky.

Řidič hledá stanici na mapě, volí termín a sleduje rezervaci. U vybraných stanic rozhoduje vlastník o žádosti; EC získává provizi 12 %. Platby a telemetrie jsou v prototypu simulované.

| Část | Dokument | Obsah |
|---|---|---|
| C01 | [Záměr a požadavky](01_zamer_a_pozadavky.md) | Project Frame, pravidla, budoucí tlak, spike a walking skeleton |
| C02 | [Specifikace](02_specifikace_operaci.md) | operace, stavy, negativní případy |
| C03 | [Architektura](03_architektura_a_rozhodnuti.md) | AS-IS, cílové mikroservisy, ADR a pohledy |
| C04 | [Kvalita](04_kvalita_a_mereni.md) | kritéria, měření, rozhodnutí |
| C05 | [Detailní návrh](05_detailni_navrh_a_testy.md) | rezervační jednotka, kontrakty, ověření |
| C06 | [Externí hodnocení](06_externi_hodnoceni.md) | projekt jiné skupiny nebyl přidělen |
| C07 | [Rizika a stav](07_rizika_a_stav.md) | registr rizik a stav projektu |
| C08 | [Řízená změna](08_rizena_zmena_a_predani.md) | schvalování vlastníkem, dopady, testy |

[Diagramy](diagramy/) obsahují kontext, strukturu prototypu, cílovou architekturu, skutečné i cílové nasazení, tři use case pohledy, komponenty, sekvenci, stavy, aktivitu, doménový a návrhový model. [Obrazovky](obrazovky/) ukazují řidiče, vlastníka a správce. [Prezentace stavu](stav_projektu.pptx) má šest snímků.

**Implementace:** modulární Spring Boot aplikace s PostgreSQL, PostGIS replikou a Redis. **Cílová architektura:** doménové mikroservisy s odděleným vlastnictvím dat a asynchronními událostmi.
