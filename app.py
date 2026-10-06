"""Welche Franchise lohnt sich? - Einstiegspunkt.

Hier steht nur der Ablauf: Seite einrichten, Daten laden, Personen einsammeln,
je Person den Bericht zeigen, am Schluss die Haushaltssumme. Gerechnet wird in
utils.py, gezeichnet in den ansicht_*-Modulen.
"""

import streamlit as st
import streamlit.components.v1 as components

from ansicht_haushalt import haushalt_summe
from ansicht_person import person_ansicht, person_eckwerte, person_formular
from basis import chf, praemien, zielgruppe_fuer_alter
from constants import KINDER_UNTERGRUPPEN, umweltabgabe_standard
from oberflaeche import farbe_fuer_person, personen_farben_setzen, seite_einrichten
from utils import get_data, kinder_beim_gleichen_versicherer

seite_einrichten()

if "_klick_kosten" in st.session_state:
    schluessel, wert = st.session_state.pop("_klick_kosten")
    st.session_state[schluessel] = wert

st.session_state.setdefault(
    "personen", [{"id": 1, "alter": 40, "unfall": "OHN-UNF", "kosten": 1000}]
)

roh = praemien(7)

st.title("Welche Franchise lohnt sich?")
st.caption(
    "Die Grundversicherung bietet mehrere Franchisen zur Auswahl. Diese App rechnet "
    "für jede Person nach, welche davon überhaupt je die günstigste ist und ab welchen "
    "jährlichen Krankheitskosten es von der einen zur anderen kippt."
)
st.info(
    f"**Prämienjahr {int(roh['Geschäftsjahr'].max())}** · Datenquelle: BAG-Prämiendaten "
    f"über opendata.swiss · Rückerstattung Umweltabgaben "
    f"**{umweltabgabe_standard * 12:.2f} CHF pro Jahr** "
    f"({umweltabgabe_standard:.2f} pro Monat), für alle Versicherten gleich und bereits "
    f"von den Prämien abgezogen.\n\n"
    f"**Rechenhilfe, keine Finanz- oder Versicherungsberatung.** Was nicht "
    f"berücksichtigt ist, steht unten auf der Seite.",
    icon="ℹ️",
)

personen = st.session_state["personen"]

# Wie viele Kinder im Haushalt leben, muss feststehen, bevor die erste Person
# gezeichnet wird - davon hängt ab, welche Tarifstufen einem Kind offenstehen.
# Die Alter stehen schon in session_state, weil Streamlit die Werte der Eingabe-
# felder über ihren Schlüssel hält; für eine eben hinzugefügte Person gibt es den
# Schlüssel noch nicht, dann gilt ihr Startwert.
def _alter_von(eintrag: dict) -> int:
    return int(st.session_state.get(f"alter_{eintrag['id']}", eintrag["alter"]))


kinder_ids = [
    e["id"] for e in personen if zielgruppe_fuer_alter(_alter_von(e)) == "Kinder"
]

personen_farben_setzen(len(personen))

aktualisiert = []
ergebnisse = []
for nummer, person in enumerate(personen, start=1):
    with st.container(border=True, key=f"person_box_{nummer}"):
        kopf = st.columns([6, 2])
        kopf[0].markdown(
            f"<span style='color:{farbe_fuer_person(nummer)}'>●</span> "
            f"**{nummer}. Person**",
            unsafe_allow_html=True,
        )

        # Ein benannter Knopf statt nur eines Pfeils: Er sagt, was er tut, und
        # steht immer an derselben Stelle - ob der Bericht gerade offen ist oder
        # nicht.
        offen_schluessel = f"offen_{person['id']}"
        offen = st.session_state.setdefault(offen_schluessel, nummer == 1)
        if kopf[1].button(
            "Einklappen" if offen else "Ausklappen",
            key=f"klapp_{person['id']}",
            width="stretch",
        ):
            st.session_state[offen_schluessel] = not offen
            st.rerun()

        eintrag = person_formular(person, len(personen), roh)
        aktualisiert.append(eintrag)

        if eintrag["wohnort"] is None:
            continue

        zielgruppe = eintrag["zielgruppe"]
        stufen = ("K1",)
        if zielgruppe == "Kinder" and offen and len(kinder_ids) > 1:
            st.caption(
                f"Kind {kinder_ids.index(person['id']) + 1} von {len(kinder_ids)}. "
                f"Unten steht dieses Kind einzeln gerechnet, zum Normaltarif K1. "
                f"Geschwisterrabatte gibt es nur, wenn **alle** Kinder beim "
                f"gleichen Versicherer sind – dazu der eigene Abschnitt weiter "
                f"unten."
            )

        if offen:
            st.markdown("---")
            ergebnis = person_ansicht(
                roh, eintrag["wohnort"][0], eintrag["wohnort"][1], zielgruppe,
                {zielgruppe: eintrag["unfall"]}, eintrag["tariftypen"], stufen,
                umweltabgabe_standard, eintrag["kosten"], person["id"], eintrag["jetzt"],
            )
        else:
            ergebnis = person_eckwerte(
                roh, eintrag["wohnort"][0], eintrag["wohnort"][1], zielgruppe,
                {zielgruppe: eintrag["unfall"]}, eintrag["tariftypen"], stufen,
                umweltabgabe_standard, eintrag["kosten"],
            )
        if ergebnis:
            ergebnis["ort"] = eintrag["wohnort"][2].split(" (")[0]
            ergebnis["id"] = person["id"]
            ergebnis["kosten"] = eintrag["kosten"]
            ergebnis["wohnort"] = eintrag["wohnort"]
            ergebnis["unfall"] = eintrag["unfall"]
            ergebnis["tariftypen"] = eintrag["tariftypen"]
            ergebnisse.append(ergebnis)

st.session_state["personen"] = [
    {k: v for k, v in p.items() if k in {"id", "alter", "unfall", "kosten"}}
    for p in aktualisiert
]

if st.button("➕ Weitere Person hinzufügen", key="person_hinzu", width="stretch"):
    naechste = max((p["id"] for p in aktualisiert), default=0) + 1
    st.session_state["personen"] = st.session_state["personen"] + [
        {"id": naechste, "alter": 8, "unfall": "MIT-UNF", "kosten": 500}
    ]
    # Die neue Person aufklappen, die übrigen zu - sonst steht man vor einer
    # Seite voller offener Berichte und sieht nicht, was eben dazugekommen ist.
    for e in aktualisiert:
        st.session_state[f"offen_{e['id']}"] = False
    st.session_state[f"offen_{naechste}"] = True
    st.session_state["_springe_zu"] = naechste
    st.rerun()

# Beim Hinzufügen einer Person dorthin springen. Streamlit hält die
# Bildlaufposition über Reruns hinweg; ohne das landet man mitten im Bericht der
# vorigen Person und sieht die neuen Eingabefelder gar nicht.
ziel = st.session_state.pop("_springe_zu", None)
if ziel is not None:
    nummer_ziel = next(
        (i for i, e in enumerate(aktualisiert, start=1) if e["id"] == ziel), None
    )
    if nummer_ziel:
        # Gescrollt wird der Hauptbereich section[data-testid="stMain"], nicht das
        # Fenster - scrollIntoView fasst den falschen Behälter an und bleibt
        # wirkungslos. Mehrere Versuche, weil Streamlit die vorherige Position
        # erst nach dem Zeichnen wiederherstellt und einen sofortigen Sprung
        # gleich wieder überschreiben würde.
        components.html(
            f"""
            <script>
              const doc = window.parent.document;
              let versuche = 0;
              const springen = () => {{
                const flaeche = doc.querySelector('section[data-testid="stMain"]');
                const kasten = doc.querySelector('.st-key-person_box_{nummer_ziel}');
                if (flaeche && kasten) {{
                  const ziel = kasten.getBoundingClientRect().top
                             - flaeche.getBoundingClientRect().top
                             + flaeche.scrollTop - 16;
                  flaeche.scrollTo({{top: ziel, behavior: 'smooth'}});
                }}
                if (++versuche < 8) setTimeout(springen, 200);
              }};
              setTimeout(springen, 120);
            </script>
            """,
            height=0,
        )

# Geschwisterrabatt: nur erhältlich, wenn alle Kinder beim gleichen Versicherer
# sind. Deshalb wird er für die Kinder gemeinsam gerechnet und gegen die freie
# Wahl ohne Rabatt gestellt - die Entscheidung gehört dem Haushalt, nicht dem
# einzelnen Kind.
gemeinsam = None
kinder_ergebnisse = [e for e in ergebnisse if e["zielgruppe"] == "Kinder"]
if len(kinder_ergebnisse) >= 2:
    erstes = kinder_ergebnisse[0]
    kinderdaten = get_data(
        roh,
        kanton=erstes["wohnort"][0],
        region=erstes["wohnort"][1],
        zielgruppen=("Kinder",),
        unfalldeckung={"Kinder": erstes["unfall"]},
        kinder_untergruppen=tuple(KINDER_UNTERGRUPPEN),
        tariftypen=tuple(erstes["tariftypen"]) if erstes["tariftypen"] else None,
    )
    gemeinsam = kinder_beim_gleichen_versicherer(
        kinderdaten,
        [float(e["kosten"]) for e in kinder_ergebnisse],
        umweltabgabe_standard,
    )

haushalt_summe(ergebnisse, len(kinder_ids), gemeinsam)

st.markdown("---")

# Dieselben Einschränkungen wie im README - wer die App benutzt, liest das
# README nicht. Eingeklappt, damit die Seite nicht mit Kleingedrucktem endet,
# aber von jeder Seite aus erreichbar.
with st.expander("Was diese Rechnung nicht berücksichtigt"):
    st.markdown(
        """
Diese Anwendung ist eine **Rechenhilfe und keine Finanz- oder
Versicherungsberatung**. Sie rechnet aus den amtlichen Prämiendaten, was die
angegebene Person bei den angegebenen Krankheitskosten zahlen würde – mehr nicht.
Welche Versicherung zu jemandem passt, hängt an Dingen, die hier nicht vorkommen:

- **Prämienverbilligung**, Zusatzversicherungen, der Spitalbeitrag von 15 CHF pro
  Tag sowie Besonderheiten einzelner Modelle.
- **Einschränkungen bei der Arztwahl.** Die alternativen Modelle sind in den
  Prämien enthalten, ihre Auflagen aber nicht bewertet. Das günstigste Angebot ist
  nicht automatisch das passendste – die günstigsten sind fast immer Modelle, die
  die Arztwahl einschränken.
- **Die Familien-Höchstgrenze** der Kostenbeteiligung (Art. 93 Abs. 3 KVV) ist in
  den Summen nicht eingerechnet. Bei drei oder mehr Kindern fällt die reale
  Belastung also tiefer aus als hier gezeigt.
- **Unterschiedliche Franchisen der Kinder.** Die Verordnung überlässt die
  Höchstbeteiligung dann dem Versicherer; hier wird eine gemeinsame Franchise
  angenommen.
- **Der Kipppunkt ist auf den Franken genau, aber dort geht es um Rappen.** Welche
  Richtung er anzeigt – hohe oder tiefe Franchise – ist belastbar, der genaue
  Betrag nicht.

Massgebend sind die Angaben der Versicherer und das offizielle
[priminfo.admin.ch](https://www.priminfo.admin.ch). Für Entscheide mit Folgen
lohnt sich eine Beratung bei einer unabhängigen Stelle.
        """
    )

spalte_links, spalte_rechts = st.columns([3, 1])
spalte_links.caption(
    "Die Prämiendaten werden beim ersten Aufruf geladen und sieben Tage "
    "zwischengespeichert."
)
if spalte_rechts.button("Prämiendaten neu laden"):
    st.cache_data.clear()
    praemien(0)
    st.rerun()

