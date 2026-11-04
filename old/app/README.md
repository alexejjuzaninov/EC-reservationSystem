# Webová ukázka

Webová ukázka aplikace C02 (`app/index.html`), zveřejněná přes GitHub Pages: <https://alexejjuzaninov.github.io/EC-reservationSystem/app/>. Je to artefakt C02: pravidla jsou kopie pravidel z `reservation.py` přepsaná do JavaScriptu a ukázka spouští stejných 40 příkladů ověření. Jedna implementace pravidel místo dvou je driver D5 pro C03. Specifikace je v `docs/specification.md`.

Ukázka je zveřejněná přes GitHub Pages: **<https://alexejjuzaninov.github.io/EC-reservationSystem/app/>**. Stačí otevřít odkaz.

Bez internetu: na GitHubu klikněte na **Code → Download ZIP**, archiv rozbalte a soubor `app/index.html` otevřete dvojklikem v prohlížeči (Chrome, Edge, Firefox). Nic se neinstaluje, data žijí jen v tomto okně: po obnovení stránky nebo tlačítkem **Začít znovu** se smažou a čas se vrátí na neděli 11. 10. 2026, 08:00 UTC.

## Nejrychlejší cesta: připravené ukázky

Nahoře v části **Připravené ukázky** klikněte na jeden ze šesti scénářů. Ukázka smaže data, sama provede několik kroků a výsledek ukáže v rozvrhu, v seznamu rezervací a v části **Co se stalo**.

| Ukázka | Co předvede |
|---|---|
| Základní průchod | vytvoření, kontrolu dostupnosti, potvrzení a zrušení jedné rezervace |
| Dva lidé, jedna stanice | návrhy se smějí překrývat, potvrzené rezervace ne; navazující čas projde |
| Limity: 4 hodiny a jednou denně | příliš dlouhá rezervace a druhá potvrzená v témže dni neprojdou |
| Schválení rychlonabíječky | rezervaci DC-1 schválí, nebo zamítne Facility admin |
| Když čas běží | po začátku rezervace ji nelze zrušit a žádost bez rozhodnutí vyprší |
| Výpadek e-mailů | Notification Service neodpovídá, potvrzení přesto platí |

## Vlastní postup krok za krokem

1. **Vyberte, za koho jednáte** (vlevo nahoře): Alice nebo Bob jsou zaměstnanci, Facility admin spravuje stanice. Všechny akce se provádějí za vybraného uživatele.
2. **Vyberte stanici, den a čas** v části **Nová rezervace**. Začátek můžete vybrat i kliknutím do volného místa v rozvrhu. Pole pod formulářem hned ukáže, zda je stanice volná a co by potvrzení odmítlo.
3. Klikněte na **Vytvořit rezervaci**. Vznikne návrh (DRAFT), stanici ještě neblokuje.
4. V seznamu **Rezervace** klikněte u návrhu na **Potvrdit**. Rezervace je CONFIRMED a stanice je v rozvrhu obsazená (zelený blok).
5. U stanice **DC-1** potvrzení jen požádá o schválení (PENDING_APPROVAL). Přepněte se na **Facility admin** a klikněte na **Schválit**, nebo **Zamítnout**.
6. Rezervaci zrušíte tlačítkem **Zrušit**. Jde to jen před jejím začátkem.

## Ovládání

| Prvek | K čemu slouží |
|---|---|
| Jednáte jako | přepíná uživatele, za kterého se provádějí akce |
| Nová rezervace | vytvoření rezervace (OP-01) a tlačítko **Ověřit dostupnost** (OP-02) |
| Rozvrh stanic | časová osa stanic AC-1, DC-1 a AC-2; šipky přepínají den, kliknutím na blok vyberete rezervaci |
| Simulovaný čas | tlačítka −1 h, +15 min, +1 h, **Na začátek vybrané** a pole **Nastavit**; červená čára v rozvrhu ukazuje „teď“ |
| Rezervace | seznam všech rezervací s akcemi podle stavu: Potvrdit, Schválit, Zamítnout, Zrušit |
| Co se stalo | historie operací: výsledek, kód chyby a pravidlo, podle kterého systém rozhodl |
| E-maily | odeslané e-maily; přepínač **Notification Service odpovídá** simuluje výpadek služby |
| Automatické ověření | dole na stránce; 40 příkladů ze specifikace, stejných jako `python reservation.py test` |

## Barvy v rozvrhu

| Vzhled bloku | Stav | Blokuje stanici? |
|---|---|---|
| šedý přerušovaný rámeček | DRAFT, návrh | ne |
| oranžové šrafování | PENDING_APPROVAL, čeká na schválení | ne |
| zelený blok | CONFIRMED, potvrzená | ano |
| přeškrtnutý nebo tečkovaný rámeček | CANCELLED, REJECTED, EXPIRED | ne |
| žlutý přerušovaný rámeček | váš výběr z formuláře | — |
| šrafovaná stopa | stanice mimo provoz (AC-2) | — |

## Pravidla, která aplikace hlídá

| Pravidlo | Co se stane při porušení |
|---|---|
| rezervaci vytváří a potvrzuje jen zaměstnanec, a to vlastní | `UNAUTHORIZED` |
| začátek musí být před koncem | `INVALID_INTERVAL` |
| rezervace trvá nejvýše 4 hodiny | `INVALID_DURATION` |
| začátek musí být v budoucnosti | `START_IN_PAST` |
| potvrzené rezervace téže stanice se nesmějí překrývat; navazující čas (konec = začátek) je v pořádku | `OVERLAP` |
| jeden uživatel má nejvýše jednu potvrzenou rezervaci za den | `DAILY_LIMIT` |
| stanici mimo provoz (AC-2) potvrdit nelze | `INACTIVE_STATION` |
| potvrdit lze jen návrh, rozhodovat jen o čekající žádosti | `INVALID_STATE` |
| po začátku rezervace ji nelze potvrdit ani zrušit | `TOO_LATE` |
| schvalovat a zamítat smí jen Facility admin | `UNAUTHORIZED` |
| o žádosti je potřeba rozhodnout do začátku rezervace | `EXPIRED` |

Odmítnutí jsou záměrná: aplikace dovolí kliknout i na akci, kterou pravidla zakazují, aby šlo předvést chybový případ. Vysvětlení se objeví v oznámení vpravo dole a v části **Co se stalo**.
