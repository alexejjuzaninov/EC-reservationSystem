# C04 · Kvalita a měření

Každý závěr platí pouze pro uvedené podmínky. Časová měření proběhla 5. 11. 2026 po zahřátí aplikace a cache, vždy jako **20 sekvenčních požadavků**. Surové hodnoty jsou v [záznamu měření](dukazy/mereni_lokalni_api.json).

| Obava | Kritérium | Měření a oracle | Výsledek | Rozhodnutí |
|---|---|---|---|---|
| Dvojí obsazení | nejvýše jeden `CONFIRMED` pro překrývající se slot | dva řidiči a paralelní rozhodnutí; HTTP + SQL | odpovědi 200/409, DB obsahuje jeden potvrzený slot | splněno pro ověřený souběh |
| Předčasná platba | `PENDING_APPROVAL` a `REJECTED` bez platebního záznamu | stav rezervace, outbox a billing v DB | platba vznikla až po `BOOKED` | splněno |
| Odezva mapy | p95 teplého dotazu pro Prahu při zoomu 11 < 250 ms | 20 GET, čas HTTP požadavku na klientu | medián 43,9 ms; p95 49,3 ms | splněno v místním měření |
| Odezva dostupnosti | p95 teplého dotazu na slot < 150 ms | 20 GET, stejný testovací stroj | medián 14,4 ms; p95 28,0 ms | splněno v místním měření |

Primární DB rozhoduje o dostupnosti; cache mapy a čtecí replika nemohou potvrdit rezervaci. Výsledky latence **neprokazují** p95 při souběžné zátěži, výpadku repliky ani pro rozsáhlý viewport USA. Před komerčním provozem je nutný zátěžový profil a test přepnutí čtení. Funkční oracly a jejich reprodukce jsou v [C05](05_detailni_navrh_a_testy.md).
