# Hohe oder tiefe Franchise?

**Die Grundversicherung bietet Erwachsenen sechs Franchisen zur Auswahl – in den Daten des
Prämienjahres 2027 sind aber nur zwei davon je die günstigste.**

Die Stufen 500, 1000, 1500 und 2000 sind bei *keinen* Krankheitskosten optimal: Es gibt
immer entweder die Franchise 300 oder die Franchise 2500, die günstiger kommt. Bei Kindern
dasselbe – nur 0 und 600 zählen, die fünf Stufen dazwischen nie. Geprüft für alle 42
Kanton/Regionen-Kombinationen der Schweiz und, in Zürich Region 1, zusätzlich für jede der
128 einzelnen Versicherer/Tarif-Kombinationen: kein einziger Fall, in dem eine mittlere
Franchise gewinnt. Über mehrere Prämienjahre hinweg beobachtet, ist das Bild stabil.

Die Wahl ist damit praktisch nicht sechsfach, sondern binär, und die eigentliche Frage
lautet: **erwarte ich viel oder wenig Krankheitskosten?** Der *Kipppunkt* ist die Schwelle
dazwischen – darunter gewinnt die höchste Franchise (tiefe Prämie), darüber die tiefste
(hohe Prämie, dafür wenig Kostenbeteiligung).

### Aber: das ist ein Befund, kein Gesetz

Die Verordnung schreibt diese Struktur **nicht** vor. Sie deckelt die Prämienreduktion
lediglich auf höchstens 70 Prozent des Risikos, das mit der höheren Franchise übernommen
wird (Art. 95 Abs. 2<sup>bis</sup> KVV); die Höhe legen die Versicherer selbst fest
„aufgrund versicherungsmässiger Erfordernisse" (Art. 95 Abs. 1<sup>bis</sup> KVV). Dass
die mittleren Stufen trotzdem nirgends gewinnen, ist also Marktverhalten, nicht Rechtsfolge
– und die Prämien werden **jedes Jahr neu festgesetzt**.

Deshalb nimmt dieses Werkzeug den Befund nirgends an, sondern rechnet ihn bei jedem Lauf
aus den aktuellen Daten neu aus. Sollte künftig eine mittlere Franchise irgendwo gewinnen,
sagt die Oberfläche das von selbst.

---

Ein kleines Werkzeug für die Schweizer Grundversicherung. Es beantwortet zwei Fragen:

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
~/.venvs/krankenkasse/bin/python main.py --kanton BE --umweltabgabe 5.15
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

Besonders wichtig ist der Befundtest: Sollte künftig doch eine mittlere Franchise
irgendwo gewinnen, ist die zentrale Aussage dieses README hinfällig – und der Workflow
sagt es, bevor es jemand anders merkt.

## Jährliche Pflege

- **Umweltabgabe** – ändert jedes Jahr. In der Oberfläche direkt eingebbar, oder als
  Standardwert `umweltabgabe_standard` in `constants.py`.
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
- Kinder haben die Altersuntergruppen `K1`, `K3`, `K4`, `K5` – **Geschwisterrabatte**,
  die das BAG nicht dokumentiert. Gemessen an `K1` (ZH, Region 1, Median über alle Tarife
  und Franchisen):

  | Stufe | Versicherer | Rabatt gegenüber `K1` | Spannweite |
  |-------|------------:|----------------------:|-----------:|
  | `K1`  | 26 (alle)   | – (Normaltarif)       | – |
  | `K3`  | 13          | 60 %                  | 10–72 % |
  | `K5`  | 4           | 25 %                  | 3–25 % |
  | `K4`  | 1 (Assura)  | 1.6 %                 | 1.3–1.9 % |

  Welche Stufe für welches Kind gilt, lässt sich aus den Daten **nicht** ableiten: Jeder
  Versicherer führt sein eigenes Schema, und ein `K2` existiert schweizweit gar nicht. Ein
  einfaches „K3 = drittes Kind" wäre also geraten. Im Haushalt-Register wird die Stufe
  deshalb pro Kind von Hand gewählt – sie steht in der Police. Nur `K1` führen alle
  Versicherer bedingungslos.

- Die Kinder-**Grundversicherung** (Standardmodell) wird ausschliesslich *ohne*
  Unfalldeckung angeboten. Wer für Kinder `MIT-UNF` filtert – die Voreinstellung –
  vergleicht deshalb nur alternative Modelle.
- Die prozentualen Prämienrabatte pro Franchisenstufe sind bundesweit geregelt. Der
  Kipppunkt fällt deshalb in verschiedenen Kantonen oft auf denselben Betrag, obwohl die
  Prämien selbst deutlich abweichen.

## Wie ernst der Kipppunkt zu nehmen ist

Kurz: weniger ernst, als die Zahl aussieht. Das Werkzeug rechnet den Kipppunkt
franken­genau aus, aber die Kostenkurven schneiden sich sehr flach. Drei Befunde, die man
kennen sollte, bevor man auf den Wert etwas gibt:

**Die Wahl zwischen den beiden lohnt sich sehr wohl.** Wer seine Krankheitskosten
realistisch einschätzt, spart gegenüber der schlechteren der beiden bis zu 1 433 CHF pro
Jahr (Erwachsene, ZH Region 1) beziehungsweise 420 CHF (Kinder). Bei 0 CHF
Krankheitskosten schlägt Franchise 2 500 die Franchise 300 um eben diese 1 433 CHF.

**Der Kipppunkt ist über die Jahre und Kantone erstaunlich stabil.** Für Erwachsene liegt
er schweizweit zwischen 1 698 und 1 926 CHF, in 32 von 44 Fällen zwischen 1 700 und
1 950 CHF (ZH Region 1: 1 892) – und über mehrere Prämienjahre hinweg bewegt er sich kaum.
Auch das ist Beobachtung, nicht Garantie: Er wird bei jedem Lauf neu berechnet.

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
