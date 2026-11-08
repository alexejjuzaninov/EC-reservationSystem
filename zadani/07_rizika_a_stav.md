# C07 · Rizika a stav projektu

**Stav k 8. 11. 2026: ŽLUTÁ.** Klíčové scénáře rezervace, schválení a mapy fungují v prototypu. Otevřené jsou týmové potvrzení nové baseline, rozsáhlejší zátěžový test a skutečné externí integrace. [Šest snímků stavu](stav_projektu.pptx) používá stejný závěr.

Hodnocení odpovídá zadání: pravděpodobnost **L** a dopad **I** mají škálu 1 nízká, 2 střední, 3 vysoká. Priorita je `L × I`; 1–2 nízká, 3–4 střední, 6–9 vysoká. Reziduum je odhad po uvedeném opatření, nikoli tvrzení o nulovém riziku.

| ID / oblast | Příčina → nejistá událost → dopad | Před | Opatření a signál | Reziduum |
|---|---|---:|---|---:|
| R1 · technická kvalita | souběžná rozhodnutí → dvojí potvrzení slotu → ztráta důvěry | 2×3=6 | zámek + GiST; sledovat konflikty a opakovat paralelní test | 1×3=3 |
| R2 · provoz | výpadek repliky/cache → pomalá mapa → horší vyhledávání | 2×2=4 | fallback na primary, cache není zdroj pravdy; sledovat p95 | 2×2=4 |
| R3 · projekt | pozdní sloučení podkladů → nesoulad verze dokumentu a kódu → slabá obhajoba | 2×2=4 | společná baseline a kontrola odkazů před odevzdáním | 1×2=2 |
| R4 · bezpečnost | demo role bez reálné identity → neoprávněná změna v produkci → zásah do rezervací | 2×3=6 | před komerčním provozem OIDC/JWT a autorizační testy | 1×3=3 |
| R5 · externí závislost | chybí platební/OCPP partner → nelze ověřit reálný provoz → omezená demonstrace | 3×2=6 | jasně označené simulace, kontrakty pro pozdější integraci | 2×2=4 |

**Monitoring:** po změně rezervace sledovat počet konfliktů 409, nevyřízené události, p95 mapy a dostupnosti. V prototypu prošla paralelní dvojice, nikoli celá zátěžová kampaň. C06 nebylo přiděleno; chybějící týmové schválení baseline zůstává otevřeným úkolem, nikoli uzavřeným rizikem.
