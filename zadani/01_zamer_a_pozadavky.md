# C01 · Záměr a požadavky

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

## Přijatá pravidla

| ID | Pravidlo |
|---|---|
| BR-01 | Rezervaci vytváří řidič; vlastník nesmí rezervovat vlastní stanici. |
| BR-02 | Termín začíná v budoucnu a trvá 30–240 minut. |
| BR-03 | Stanice je aktivní a zveřejněná; termín respektuje otevírací dobu a blokace. |
| BR-04 | Dvě potvrzené rezervace stejné stanice se nesmějí časově překrývat. |
| BR-05 | U stanice se schvalováním rozhoduje jen její vlastník před začátkem termínu. |
| BR-06 | Platební simulace vzniká až po potvrzení; čekání a zamítnutí ji nevytváří. |

## Tlak na návrh

| Typ | Konkrétní důsledek |
|---|---|
| Q · kvalita | rozhodnutí o slotu musí být atomické i při souběhu řidičů |
| C · kapacita | mapu je nutné agregovat prostorově a kešovat clustery |
| R · spolehlivost | čtení mapy používá repliku; konečné rozhodnutí používá primární DB |
| L · omezení | platby a telemetrie jsou označené simulace, nikoli externí transakce |

**Průchozí kostra:** výběr stanice → dostupnost → návrh → potvrzení nebo žádost → rozhodnutí vlastníka → oznámení. Při technickém spike měla žádost stav `PENDING_APPROVAL` bez platby; po schválení přešla do `CONFIRMED` a druhé potvrzení stejného slotu skončilo konfliktem 409. Podrobné oracly jsou v [C05](05_detailni_navrh_a_testy.md).
