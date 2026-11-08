# Kontrolní matice

Podklady se vztahují k pracovní verzi projektu založené na commitu `6fa569b` a migraci V22. Formální výstupy jsou v této složce.

| Část | Požadovaný výstup | Důkaz | Stav |
|---|---|---|---|
| C01 | tým, doména, hranice, Q/C/R/L, spike | [01](01_zamer_a_pozadavky.md) | doloženo; podpis týmu chybí |
| C02 | čtyři operace, změna, pravidla, stavy, negativní scénáře | [02](02_specifikace_operaci.md), [stavy](diagramy/08_stavy.png), [aktivita](diagramy/09_aktivita.png) | implementováno a ověřeno |
| C03 A | scénář a skutečná struktura | [AS-IS](diagramy/00_as_is.png), [03](03_architektura_a_rozhodnuti.md) | doloženo |
| C03 | drivery, varianty, ADR, kontext, struktura, sekvence, model | [03](03_architektura_a_rozhodnuti.md), [diagramy](diagramy/) | cílový návrh oddělen od prototypu |
| C04 | obava → kritérium → měření → rozhodnutí | [04](04_kvalita_a_mereni.md), [výsledky](dukazy/mereni_lokalni_api.json) | lokálně změřeno; zátěžový test chybí |
| C05 | jednotka, kontrakty, algoritmus, testy, shoda s kódem | [05](05_detailni_navrh_a_testy.md), [záznamy](dukazy/) | ověřeno pro uvedené scénáře |
| C06 | externí hodnocení jiné skupiny | [06](06_interni_hodnoceni.md) | nepřiděleno; nelze vykázat jako provedeno |
| C07 | ≥4 rizika ve ≥3 oblastech, rezidua, stav, šest snímků | [07](07_rizika_a_stav.md), [prezentace](stav_projektu.pptx) | doloženo |
| C08 | změna, dopady, varianty, dva testy s oraclem, předání | [08](08_rizena_zmena_a_predani.md) | rozhodnutí přijato; týmová revize není doložena |

**Otevřené formální důkazy:** potvrzení společné baseline a jméno kritického recenzenta změny. Výsledky testů tato schválení nenahrazují.
