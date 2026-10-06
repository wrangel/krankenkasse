# Welche Franchise lohnt sich?

Ein kleines Werkzeug für die Schweizer Grundversicherung. Es rechnet aus den offiziellen
BAG-Prämiendaten für jede wählbare Franchise die Gesamtkosten eines Jahres aus – über den
ganzen Bereich möglicher Krankheitskosten – und zeigt, welche davon wann die günstigste
ist. Welche das sind und wie viele es sind, ergibt sich aus den Daten; vorausgesetzt wird
nichts.

Es beantwortet drei Fragen:

1. **Welche Kasse bietet pro Franchise die günstigste Prämie?** – für einen bestimmten
   Kanton, eine Prämienregion und eine Altersklasse.
2. **Ab welchen jährlichen Krankheitskosten lohnt sich die tiefste Franchise?** – der
   *Kipppunkt*, unter Einbezug der Umweltabgabe, die pro Person und Monat von der Prämie
   abgezogen wird.
3. **Was kostet der ganze Haushalt bei welchem Versicherer?** – Erwachsene, Jugendliche
   und Kinder zusammen, inklusive Geschwisterrabatten und der Familien-Höchstgrenze bei
   der Kostenbeteiligung.

Die Daten stammen direkt aus dem offiziellen Prämienvergleich des Bundesamts für
Gesundheit, bezogen über
[opendata.swiss](https://opendata.swiss/de/dataset/health-insurance-premiums), und
werden bei jedem Lauf
aktuell geladen.

## Wie gerechnet wird

Für jede Franchise werden die effektiven Gesamtkosten eines Jahres bestimmt:

```
Jahreskosten = 12 × (Monatsprämie − Umweltabgabe)
             + min(Krankheitskosten, Franchise)          ← Franchise-Anteil
             + min(10 % der Kosten über der Franchise,
                   Höchstgrenze)                          ← Selbstbehalt
```

Die Höchstgrenze des Selbstbehalts beträgt gemäss Art. 103 KVV 700 CHF pro Jahr für
Erwachsene und Jugendliche, 350 CHF für Kinder.

Anschliessend wird für jeden Kostenbetrag ermittelt, welche Franchise am günstigsten ist.
Der Kipppunkt ist der tiefste Betrag, ab dem die **tiefste** Franchise gewinnt.

## Installation

Benötigt Python 3.12 oder neuer.

```bash
git clone https://github.com/wrangel/krankenkasse.git
cd krankenkasse
python3 -m venv ~/.venvs/krankenkasse
~/.venvs/krankenkasse/bin/pip install -r requirements.txt
```

Die virtuelle Umgebung liegt hier bewusst ausserhalb des Projektordners – so wird sie
weder von Cloud-Diensten synchronisiert noch versehentlich eingecheckt. Ein Pfad innerhalb
des Projekts (`python3 -m venv venv`) funktioniert genauso gut.

## Benutzung

### Grafische Oberfläche

```bash
~/.venvs/krankenkasse/bin/streamlit run app.py
```

Öffnet <http://localhost:8501>. Kanton, Prämienregion, Umweltabgabe, Zielgruppen und die
erwarteten Krankheitskosten werden direkt im Fenster eingestellt. Es gibt zwei Register:

**Einzelperson**

- den Kipppunkt pro Zielgruppe,
- die Kostenkurven aller Franchisen als Diagramm,
- das günstigste Angebot pro Franchise samt Versicherer und Tarifmodell,
- einen direkten Vergleich bei den tatsächlich erwarteten Krankheitskosten,
- die Kostenmatrix als CSV-Download.

**Haushalt**

Erwachsene, Jugendliche und Kinder werden zusammengezählt und die **Jahresprämie des
ganzen Haushalts** je Versicherer verglichen. Für jedes Kind wird die Tarifstufe einzeln
gewählt (siehe unten) – berücksichtigt werden nur Anbieter, die *alle* verlangten
Kategorien führen. Das ist der ehrliche Familienvergleich: ein Versicherer mit günstigen
Erwachsenenprämien, aber ohne Geschwisterrabatt, kann für einen Haushalt teurer sein als
einer mit Rabatt – und umgekehrt gewinnt ein sehr günstiger Grundtarif auch ohne
Geschwisterrabatt. Ab zwei Kindern wird zusätzlich die Familien-Höchstgrenze der
Kostenbeteiligung ausgewiesen.

### Kommandozeile

```bash
~/.venvs/krankenkasse/bin/python main.py
~/.venvs/krankenkasse/bin/python main.py --kanton BE --umweltabgabe 4.75
```

Optionen: `--kanton`, `--region`, `--umweltabgabe`, `--max-kosten`.

## Abhängigkeiten und Tests

`requirements.txt` pinnt die fünf direkten Abhängigkeiten exakt.
[Dependabot](.github/dependabot.yml) schlägt monatlich Aktualisierungen vor – gruppiert,
also ein Pull Request statt einer pro Paket, für pip und für die GitHub Actions selbst.

Damit eine grüne Prüfung an so einem Pull Request etwas aussagt, rechnet
`test_berechnung.py` mit erfundenen Prämien nach: Kostenformel, Kipppunkt, dominierte
Franchisen, der Selbstbehalt-Deckel und die Familien-Höchstgrenze. Die Erwartungswerte
sind von Hand gerechnet und im Test hergeleitet, nicht aus dem Code abgelesen.

```bash
python test_berechnung.py     # ohne Netz, ohne pytest
```

Das schliesst die Lücke, die Installations- und Kompilierprüfungen offenlassen: Die ganze
App ist eine Rechenkette über pandas. Änderte sich das Verhalten von `groupby`, `idxmin`
oder `str.extract`, käme klaglos ein falscher Kipppunkt heraus, ohne dass Installation
oder Kompilierung etwas merken.

## Überwachung der Datenquellen

Beim Wechsel auf das Prämienjahr 2027 hat sich gezeigt, wie nötig das ist – und wie
schlecht sich Vorhersagen darüber machen lassen, *wie* eine Quelle bricht. Erwartet worden
war, dass der Prämienvergleich unter festem Pfad stillschweigend neue Inhalte bekommt und
das Versichererverzeichnis auf einen 404 läuft. Eingetreten ist das Gegenteil: Der
vermeintlich feste Pfad `priminfo.admin.ch/downloads/gesamtbericht_ch.xlsx` wurde
abgeschaltet, das Verzeichnis blieb erreichbar. Zusätzlich änderte sich praktisch alles
andere mit:

| | bis 2026 | ab 2027 |
|---|---|---|
| Ablage | priminfo.admin.ch | opendata.swiss |
| Blattname | `Export` | `Sheet1` |
| Region | `PR-REG CH1` | `PR_REG_1` |
| Altersklasse | `AKL-ERW` | `AKA_03_ERW` |
| Unfalleinschluss | `OHN-UNF` | `OHN_UNF` |
| Franchise | `FRA-300` | `FRA_01_E_0300` |
| Altersuntergruppe | bei Erwachsenen leer | `E1` / `J1` |
| Tariftypen | `TAR-BASE`, `TAR-HAM`, `TAR-HMO`, `TAR-DIV` | `BASE`, `PRAXIS`, `FLEX`, `TEL_DIG`, `PHARM` |
| `isBaseP` | markierte Dubletten (0 = doppelfreie Tabelle) | schlichtes Kennzeichen (1 = Base-Tarif) |

Die letzte Zeile war die gefährlichste: Der bisherige Filter `isBaseP == 0` hätte ab 2027
sämtliche Standardtarife verworfen – klaglos, ohne Fehlermeldung, mit plausibel
aussehenden Zahlen. `lade_praemien` entdoppelt deshalb neu über den fachlichen Schlüssel,
und `_normalisiere_codes` führt die neuen Schreibweisen auf die bisherigen zurück, damit
der übrige Code eine einzige Sprache spricht.

`pruefe_datenquellen.py` vergleicht gegen den in
`datenstand.json` festgehaltenen Stand: Erreichbarkeit, Prämienjahr, Spalten,
Altersklassen, Altersuntergruppen, Franchisenstufen – und den zentralen Befund, dass nur
die höchste und die tiefste Franchise je optimal sind.

```bash
python pruefe_datenquellen.py              # prüfen (Exit-Code 1 bei Abweichung)
python pruefe_datenquellen.py --schreiben   # neuen Stand festhalten
```

Der Workflow [`datenquellen.yml`](.github/workflows/datenquellen.yml) führt das
automatisch aus: wöchentlich, und im September/Oktober täglich – dann veröffentlicht das
BAG die Prämien des Folgejahres. Schlägt der Lauf fehl, benachrichtigt GitHub den
Repository-Besitzer. Damit meldet sich das Projekt von selbst, statt still falsche Zahlen
zu zeigen.

Dabei werden zwei Dinge streng auseinandergehalten:

- **Handlungsbedarf an den Quellen** – tote URL, umbenannte Spalte, neues Prämienjahr,
  verändertes Kennzeichen. Das macht das Werkzeug kaputt oder verfälscht es still. Die
  Prüfung schlägt fehl, GitHub benachrichtigt.
- **Ein anderer Befund** – welche Franchisen je die günstigsten sind, wo der Kipppunkt
  liegt. Die Prüfung bleibt **grün**; der Befund erscheint als Warnung und in der
  Zusammenfassung des Laufs.

Der Unterschied ist kein Detail. Dass bisher nur die höchste und die tiefste Franchise je
gewonnen haben, ist eine **Beobachtung über einzelne Prämienjahre, kein Sollwert**. Die
Prämien werden jedes Jahr neu festgesetzt, und was sich lohnt, folgt aus ihnen – nicht
umgekehrt. Ein Werkzeug, das ein verändertes Ergebnis als Fehlschlag meldet, würde eine
Hypothese verteidigen, statt zu rechnen. Ändert sich der Befund, hat nichts versagt; dann
ist bloss die Beschreibung in README und Oberfläche veraltet.

`datenstand.json` ist deshalb ein Gedächtnis, kein Sollwert: Es hält fest, was zuletzt
beobachtet wurde, damit Veränderung überhaupt auffällt.

Aus demselben Grund steht in der Oberfläche nirgends fest verdrahtet, dass nur zwei
Franchisen zählen. Die Meldung wird aus `nie_optimal` erzeugt, also aus den geladenen
Daten; ergibt sich etwas anderes, sagt die Oberfläche etwas anderes. Auch
`test_berechnung.py` prüft nie die These selbst, sondern nur die Mechanik – mit
erfundenen Prämien, bei denen von Hand nachgerechnet ist, welche Franchise dominiert.

## Was beim Jahreswechsel zu tun ist

Das BAG veröffentlicht die Prämien des Folgejahres Ende September. Die Überwachung läuft
in diesen Wochen täglich und meldet sich von selbst. Der Ablauf:

1. **Die Prüfung schlägt fehl** – neues Prämienjahr, oft zusammen mit geänderten URLs
   oder Codes. Die Meldung sagt, was sich verschoben hat.
2. **Nachführen**: Download-Adresse und Schreibweisen in `constants.py` bzw.
   `_normalisiere_codes`, die Umweltabgabe für das neue Jahr, und ein Blick darauf, ob
   `versicherer.json` noch alle Versicherer kennt.
3. **Festhalten**:

   ```bash
   python pruefe_datenquellen.py --schreiben
   ```

   Das überschreibt `datenstand.json` (immer nur das Jetzt) und **ergänzt**
   `befund_historie.json` um einen Eintrag für das neue Prämienjahr.

`befund_historie.json` ist der einzige Teil, der wächst: ein Eintrag pro Jahr mit den je
günstigsten Franchisen und dem Kipppunkt. Damit entsteht über die Jahre eine Reihe, an der
sich die Beobachtung aus dem Abschnitt weiter unten tatsächlich prüfen lässt – statt sie
aus der Erinnerung zu behaupten. Die Reihe beginnt beim Prämienjahr 2027; frühere Jahre
sind bewusst nicht nachgetragen, weil sie aus einer anderen Quelle mit anderer
Entdoppelung stammen und nicht vergleichbar wären.

## Jährliche Pflege

- **Umweltabgabe** – die Rückerstattung ändert jedes Jahr (2027: 57.00 CHF pro Person und
  Jahr, also 4.75 pro Monat; 2026 waren es 61.80 bzw. 5.15). In der Oberfläche direkt
  eingebbar, oder als Standardwert `umweltabgabe_standard` in `constants.py`. Den
  Kipppunkt verschiebt der Wert nicht, wohl aber alle absoluten Beträge.
- **Versicherernamen** – `versicherer.json` stammt aus dem
  [BAG-Verzeichnis der zugelassenen Krankenversicherer](https://www.bag.admin.ch/de/verzeichnisse-der-zugelassenen-kranken-und-rueckversicherer).
  Die Download-URL enthält einen jährlich wechselnden Hash: neue URL ablesen, in
  `refresh_versicherer.py` eintragen und ausführen.
- **Prämiendaten** – werden automatisch geladen und sieben Tage lang unter `.cache/`
  zwischengespeichert. In der Oberfläche erzwingt *Prämiendaten neu laden* einen Neuabruf.

## Hinweise zu den Daten

- Der Filter `isBaseP == 0` entfernt **Duplikate**: Standardtarife (`TAR-BASE`) sind in der
  BAG-Tabelle doppelt vorhanden. Es werden also alle Tarifmodelle berücksichtigt, nicht nur
  die alternativen.
- Kinder haben die Altersuntergruppen `K1`, `K3`, `K4`, `K5` – **Geschwisterrabatte**.
  Ihre Bedeutung steht in der Tarifliste des BAG (`Tarife.xlsx` auf opendata.swiss,
  Kategorie `ALT`):

  | Stufe | Bedeutung laut BAG | Versicherer | Rabatt gegenüber `K1` |
  |-------|--------------------|------------:|----------------------:|
  | `K1`  | ohne zusätzlichen Rabatt | 26 (alle) | – (Normaltarif) |
  | `K3`  | Rabatt ab dem 3. Kind | 13 | 60 % |
  | `K4`  | Rabatt ab dem **2.** Kind, gültig für alle Kinder | 1 | 1.6 % |
  | `K5`  | Rabatt ab dem 3. Kind, gültig für alle Kinder | 4 | 25 % |

  Die Rabattwerte sind Mediane über alle Tarife und Franchisen in ZH Region 1. Beachte,
  dass `K4` den Rabatt ab dem **zweiten** Kind meint, nicht ab dem vierten – die Zahl im
  Code ist eine Stufennummer, keine Kinderzahl. Ein `K2` existiert schweizweit nicht.
  Welche Stufe gilt, hängt vom Versicherer und der Zahl der Kinder derselben Familie ab
  und steht in der Police; nur `K1` führen alle Versicherer bedingungslos.

- Die Kinder-**Grundversicherung** (Standardmodell) wird ausschliesslich *ohne*
  Unfalldeckung angeboten. Wer für Kinder `MIT-UNF` filtert – die Voreinstellung –
  vergleicht deshalb nur alternative Modelle.
- Die prozentualen Prämienrabatte pro Franchisenstufe sind bundesweit geregelt. Der
  Kipppunkt fällt deshalb in verschiedenen Kantonen oft auf denselben Betrag, obwohl die
  Prämien selbst deutlich abweichen.

## Eine Beobachtung am Rande

Dieser Abschnitt gehört nicht zum Werkzeug, sondern beschreibt, was bei seiner Benutzung
bisher herausgekommen ist. Er ist Beobachtung, keine Annahme – gerechnet wird in jedem
Fall aus den geladenen Daten.

Die laufend fortgeschriebene Reihe steht in
[`befund_historie.json`](befund_historie.json) – ein Eintrag pro Prämienjahr, ab 2027.

**Bisher gewannen nur die höchste und die tiefste Franchise.** Im Prämienjahr 2027 sind
die Stufen 500, 1000, 1500 und 2000 bei *keinen* Krankheitskosten optimal; es kommt immer
entweder die Franchise 300 oder die 2500 günstiger. Bei Kindern dasselbe – nur 0 und 600,
die fünf Stufen dazwischen nie. Nachgerechnet für alle 42 Kanton/Regionen-Kombinationen
und, in Zürich Region 1, zusätzlich für jede der 128 einzelnen
Versicherer/Tarif-Kombinationen: kein Gegenbeispiel. Über mehrere Prämienjahre hinweg
betrachtet ist das Bild stabil geblieben.

**Die Verordnung schreibt das nicht vor.** Sie deckelt die Prämienreduktion lediglich auf
höchstens 70 Prozent des Risikos, das mit der höheren Franchise übernommen wird
(Art. 95 Abs. 2<sup>bis</sup> KVV); die Höhe legen die Versicherer selbst fest „aufgrund
versicherungsmässiger Erfordernisse" (Art. 95 Abs. 1<sup>bis</sup> KVV). Dass die
mittleren Stufen trotzdem nirgends gewinnen, ist Marktverhalten, nicht Rechtsfolge – und
die Prämien werden jedes Jahr neu festgesetzt. Die Beobachtung kann also jederzeit
aufhören zu gelten, ohne dass irgendetwas falsch gelaufen wäre.

**Der Kipppunkt ist bisher erstaunlich stabil.** Für Erwachsene liegt er schweizweit
zwischen 1 698 und 1 926 CHF, in 32 von 44 Fällen zwischen 1 700 und 1 950 CHF
(ZH Region 1: 1 893 für 2027, 1 892 für 2026).

## Wie ernst der Kipppunkt zu nehmen ist

Kurz: weniger ernst, als die Zahl aussieht. Das Werkzeug rechnet den Kipppunkt
franken­genau aus, aber die Kostenkurven schneiden sich sehr flach. Zwei Dinge, die man
kennen sollte, bevor man auf den Wert etwas gibt:

**Die Wahl zwischen den beiden lohnt sich sehr wohl.** Wer seine Krankheitskosten
realistisch einschätzt, spart gegenüber der schlechteren der beiden bis zu 1 433 CHF pro
Jahr (Erwachsene, ZH Region 1) beziehungsweise 420 CHF (Kinder). Bei 0 CHF
Krankheitskosten schlägt Franchise 2 500 die Franchise 300 um eben diese 1 433 CHF.

**Aber benachbarte Stufen liegen eng beieinander.** Gegenüber der *nächstbesten* Stufe
bringt die tiefste Franchise höchstens rund 70 CHF pro Jahr (Erwachsene) beziehungsweise
30 CHF (Kinder). Die prozentualen Prämienrabatte pro Franchisenstufe sind bundesweit
geregelt und offenbar so kalibriert, dass sich aufeinanderfolgende Stufen fast die Waage
halten. Genau deshalb ist der Kipppunkt unscharf: Es geht um die Richtung – hohe oder
tiefe Franchise –, nicht um den Franken.

**Zum Vergleich die Wahl des Versicherers.** Bei identischer Franchise liegen zwischen dem
günstigsten und dem teuersten Anbieter über 2 000 CHF pro Jahr, also nochmals mehr als die
Franchisenwahl. Beide Hebel lohnen sich; die Oberfläche zeigt beide Spannweiten an.

**Die Umweltabgabe verschiebt den Kipppunkt nicht.** Sie wird von jeder Prämie gleich
abgezogen, verschiebt also alle Kostenkurven um denselben Betrag `12 × Abgabe` nach unten
und lässt die Reihenfolge unverändert. Sie beeinflusst nur die absoluten Frankenbeträge.
Dasselbe gilt für die Prämienverbilligung. Der jährliche Neueintrag lohnt sich also für
korrekte Gesamtkosten, ändert an der Franchisenempfehlung aber nichts.

Statt allein auf den Kipppunkt zu schauen, bietet die Oberfläche deshalb eine
**Spürbarkeitsschwelle**: ab wann der Vorteil einen selbst gewählten Betrag pro Jahr
überschreitet.

## Was nicht berücksichtigt ist

- **Prämienverbilligung**, Zusatzversicherungen, der Spitalbeitrag von 15 CHF pro Tag
  sowie Bonus- und Hausarztmodell-Besonderheiten.
- **Die Kipppunkt-Analyse rechnet weiterhin pro Person.** Die Familien-Höchstgrenze
  (Art. 93 Abs. 3 KVV) wird nur im Haushalt-Register ausgewiesen, nicht in die
  Kostenkurven eingerechnet. Für Familien mit drei oder mehr Kindern liegt die reale
  Kostenbeteiligung deshalb tiefer, als die Einzelperson-Kurven vermuten lassen.
- **Unterschiedliche Franchisen der Kinder.** Die Verordnung überlässt die
  Höchstbeteiligung dann dem Versicherer; das Werkzeug nimmt eine gemeinsame Franchise an.
- **Einschränkungen bei der Arztwahl.** Alternative Modelle (HMO, Hausarzt, Telmed) sind
  in den Prämien enthalten, ihre Auflagen aber nicht bewertet. Die günstigste Prämie ist
  nicht automatisch das passendste Modell.

Das Werkzeug ist eine Rechenhilfe und keine Finanz- oder Versicherungsberatung.

## Lizenz

[MIT](LICENSE) – Copyright (c) 2023-2026 Matthias Wettstein.

Die Prämiendaten stammen vom Bundesamt für Gesundheit und unterliegen dessen
Nutzungsbedingungen.

## Im Container betreiben

```bash
docker compose up -d --build
```

Danach läuft die App auf Port 8501. Für den Betrieb auf einer Synology ist
`platform: linux/amd64` gesetzt – ohne das baut ein Apple-Rechner ein
arm64-Abbild, das dort nicht startet.

Die Prämiendatei des BAG (rund 12 MB) wird beim ersten Aufruf geladen und liegt
im Volume `praemien-cache`. Dadurch kostet ein Neustart nicht jedes Mal die rund
sechs Sekunden fürs Einlesen.

**Zum Testen auf einem Apple-Rechner:** Ein `linux/amd64`-Abbild läuft dort unter
Emulation, und pandas stürzt darin mit einem Speicherzugriffsfehler ab
(`qemu: uncaught target signal 11`). Das ist eine Eigenheit der Emulation, nicht
des Abbilds. Lokal prüfen lässt es sich mit einem Bau für die eigene
Architektur:

```bash
docker build -t krankenkasse:lokal .
docker run --rm -p 8501:8501 krankenkasse:lokal
```
