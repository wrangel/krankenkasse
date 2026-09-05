# Krankenkassen-Kipppunkt

Ein kleines Werkzeug für die Schweizer Grundversicherung. Es beantwortet zwei Fragen:

1. **Welche Kasse bietet pro Franchise die günstigste Prämie?** – für einen bestimmten
   Kanton, eine Prämienregion und eine Altersklasse.
2. **Ab welchen jährlichen Krankheitskosten lohnt sich die tiefste Franchise?** – der
   *Kipppunkt*, unter Einbezug der Umweltabgabe, die pro Person und Monat von der Prämie
   abgezogen wird.

Die Daten stammen direkt aus dem offiziellen Prämienvergleich des Bundesamts für
Gesundheit ([priminfo.admin.ch](https://www.priminfo.admin.ch)) und werden bei jedem Lauf
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
erwarteten Krankheitskosten werden direkt im Fenster eingestellt. Die Oberfläche zeigt:

- den Kipppunkt pro Zielgruppe,
- die Kostenkurven aller Franchisen als Diagramm,
- das günstigste Angebot pro Franchise samt Versicherer und Tarifmodell,
- einen direkten Vergleich bei den tatsächlich erwarteten Krankheitskosten,
- die Kostenmatrix als CSV-Download.

### Kommandozeile

```bash
~/.venvs/krankenkasse/bin/python main.py
~/.venvs/krankenkasse/bin/python main.py --kanton BE --umweltabgabe 5.15
```

Optionen: `--kanton`, `--region`, `--umweltabgabe`, `--max-kosten`.

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
- Kinder haben die Altersuntergruppen `K1`, `K3`, `K4`, `K5`. Diese sind nicht offiziell
  dokumentiert. `K1` ist der Normalfall, `K3` und `K5` enthalten Familienrabatte für
  weitere Kinder. Standardauswahl ist `K1` + `K4`; in der Oberfläche unter
  *Feineinstellungen* änderbar.
- Die prozentualen Prämienrabatte pro Franchisenstufe sind bundesweit geregelt. Der
  Kipppunkt fällt deshalb in verschiedenen Kantonen oft auf denselben Betrag, obwohl die
  Prämien selbst deutlich abweichen.

## Wie ernst der Kipppunkt zu nehmen ist

Kurz: weniger ernst, als die Zahl aussieht. Das Werkzeug rechnet den Kipppunkt
franken­genau aus, aber die Kostenkurven schneiden sich sehr flach. Drei Befunde, die man
kennen sollte, bevor man auf den Wert etwas gibt:

**Der Unterschied ist klein.** Über den ganzen Bereich bis 10 000 CHF bringt die tiefste
Franchise gegenüber der nächstbesten Stufe höchstens rund 70 CHF pro Jahr (Erwachsene,
ZH Region 1) beziehungsweise 30 CHF (Kinder). Die prozentualen Prämienrabatte pro
Franchisenstufe sind bundesweit geregelt und offenbar so kalibriert, dass sich die
Varianten fast die Waage halten. Unmittelbar am Kipppunkt geht es um Rappen.

**Die Wahl des Versicherers wiegt viel schwerer.** Bei identischer Franchise liegen
zwischen dem günstigsten und dem teuersten Anbieter über 2 000 CHF pro Jahr. Wer sparen
will, wechselt die Kasse, nicht die Franchise. Deshalb zeigt die Oberfläche die
Spannweite prominent an.

**Die Umweltabgabe verschiebt den Kipppunkt nicht.** Sie wird von jeder Prämie gleich
abgezogen, verschiebt also alle Kostenkurven um denselben Betrag `12 × Abgabe` nach unten
und lässt die Reihenfolge unverändert. Sie beeinflusst nur die absoluten Frankenbeträge.
Dasselbe gilt für die Prämienverbilligung. Der jährliche Neueintrag lohnt sich also für
korrekte Gesamtkosten, ändert an der Franchisenempfehlung aber nichts.

Statt allein auf den Kipppunkt zu schauen, bietet die Oberfläche deshalb eine
**Spürbarkeitsschwelle**: ab wann der Vorteil einen selbst gewählten Betrag pro Jahr
überschreitet.

## Was nicht berücksichtigt ist

- **Familien-Höchstgrenze.** Sind mehrere Kinder einer Familie beim gleichen Versicherer
  versichert, darf ihre Kostenbeteiligung zusammen das Zweifache des Höchstbetrages je
  Kind nicht übersteigen (Art. 93 Abs. 3 KVV; bei der ordentlichen Franchise Art. 64
  Abs. 4 KVG). Das Werkzeug rechnet pro Person und bildet diese Deckelung nicht ab – für
  Familien mit mehreren Kindern fällt die reale Belastung tiefer aus.
- **Prämienverbilligung**, Zusatzversicherungen, der Spitalbeitrag von 15 CHF pro Tag
  sowie Bonus- und Hausarztmodell-Besonderheiten.
- **Einschränkungen bei der Arztwahl.** Alternative Modelle (HMO, Hausarzt, Telmed) sind
  in den Prämien enthalten, ihre Auflagen aber nicht bewertet. Die günstigste Prämie ist
  nicht automatisch das passendste Modell.

Das Werkzeug ist eine Rechenhilfe und keine Finanz- oder Versicherungsberatung.

## Lizenz

[MIT](LICENSE) – Copyright (c) 2023-2026 Matthias Wettstein.

Die Prämiendaten stammen vom Bundesamt für Gesundheit und unterliegen dessen
Nutzungsbedingungen.
