# Yasl für Home Assistant

Deine [Yasl](https://yasl.resolved-it.de)-Einkaufslisten als To-do-Listen in Home Assistant: abhaken, hinzufügen,
umbenennen, sortieren und löschen direkt im Dashboard, in der Seitenleiste unter **To-do-Listen** und in Automationen.
Änderungen erscheinen sofort in der Yasl-App aller Mitglieder der Liste.

*English below.*

## Installation

1. In HACS: **⋮ → Benutzerdefinierte Repositories**, URL `https://github.com/Resolved-IT/ha-yasl`, Typ **Integration**.
2. **Yasl** suchen, herunterladen und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Yasl**. Es öffnet sich Yasl: anmelden (falls nötig) und
   **Erlauben** tippen. Client-ID oder API-Schlüssel brauchst du nicht.

Jede Liste deines Kontos (eigene, geteilte, Haushaltslisten) wird eine Entität `todo.yasl_…`. Neue Listen erscheinen
von selbst, gelöschte verschwinden.

## Im Dashboard

Karte hinzufügen → **To-do-Liste** → deine Yasl-Liste wählen. Abgehakte Artikel stehen unten und lassen sich dort
auch löschen.

## Menge und Einheit

Menge und Einheit stehen in Klammern hinter dem Namen und lassen sich beim Bearbeiten ändern:
`Milch (2 l)`, `Eier (6×)`, `Mehl (1,5 kg)`. Ohne Klammer ist es ein Stück. Die Notiz eines Artikels ist die
Beschreibung des To-do-Eintrags.

## Kontingent

Die Integration fragt deine Listen alle 30 Sekunden ab; diese Abfragen zählen **nicht** gegen das Tageslimit des
Free-Tarifs. Änderungen (hinzufügen, abhaken, löschen, sortieren) zählen wie jede API-Anfrage: im Free-Tarif 10 pro
Tag, mit Yasl Plus unbegrenzt.

## Trennen

In Yasl unter **Profil → Integrationen** siehst du die Verbindung „Home Assistant“ und kannst sie jederzeit trennen.
Home Assistant bittet dann um eine neue Anmeldung.

---

# Yasl for Home Assistant (English)

Your [Yasl](https://yasl.resolved-it.de) shopping lists as to-do lists in Home Assistant: check off, add, rename, sort
and delete items on the dashboard, under **To-do lists** and in automations. Changes appear instantly in the Yasl app
of every list member.

**Install:** HACS → ⋮ → Custom repositories → `https://github.com/Resolved-IT/ha-yasl` (type Integration), download
**Yasl**, restart, then add the integration **Yasl** and tap **Allow** in Yasl. No client id or API key needed.

**Quantity and unit** go in brackets after the name: `Milk (2 l)`, `Eggs (6×)`. The item's note is the to-do
description.

**Quota:** the integration polls every 30 seconds; these reads do not count against the free plan's daily limit.
Changes count like any API request (free: 10 per day, Yasl Plus: unlimited).

**Disconnect** any time in Yasl under Profile → Integrations.

## License

MIT
