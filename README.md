# Better Dashboard Roles

Better Dashboard Roles ist eine HACS-kompatible Home-Assistant Custom Integration mit einer kleinen Lovelace Frontend-Resource. Das Plugin filtert Dashboard-Links in der Sidebar anhand von Gruppen/Rollen und kann Benutzer auf ein Gruppen-Default-Dashboard umleiten.

## Wichtiger Sicherheitshinweis

Dieses Plugin ist keine echte Zugriffskontrolle.

Es versteckt und redirectet nur im Home-Assistant Frontend. Entitäten, Dashboards, APIs und Views sind technisch weiterhin erreichbar, wenn Home Assistant selbst sie erlaubt. Für echte Sicherheit müssen eigene Home-Assistant-Instanzen, Netzwerktrennung, separate Benutzerrechte, Reverse-Proxy-Regeln oder andere echte Zugriffskontrollen verwendet werden.

## Funktionen

- YAML-Konfiguration in `configuration.yaml`
- Backend-Endpoint: `GET /api/better_dashboard_roles/config`
- Sidebar-Dashboard-Links anhand erlaubter Gruppen oder Rollen ausblenden
- Optionaler Redirect von blockierten Dashboard-URLs
- Optionales Ausblenden typischer Admin-/Einstellungsmenüs für Nicht-Admin-Rollen
- Robust gegen dynamisch gerenderte Home-Assistant Sidebar per `MutationObserver`
- Keine npm-Abhängigkeiten, kein Build-System, Vanilla JavaScript

## Installation über HACS

1. HACS öffnen.
2. `Integrations` öffnen.
3. Rechts oben `Custom repositories` öffnen.
4. Repository-URL eintragen.
5. Kategorie `Integration` wählen.
6. `Better Dashboard Roles` installieren.
7. Home Assistant neu starten.
8. Unter `Einstellungen` -> `Geräte & Dienste` -> `Integration hinzufügen` die Integration `Better Dashboard Roles` hinzufügen.

Hinweis: Dieses Repository enthält zusätzlich die Datei `www/better-dashboard-roles.js`. Falls HACS sie in deiner Installation nicht automatisch nach `config/www/` legt, kopiere sie manuell nach:

```text
config/www/better-dashboard-roles.js
```

## Lovelace Resource hinzufügen

Füge in Home Assistant unter `Einstellungen` -> `Dashboards` -> Drei-Punkte-Menü -> `Ressourcen` folgende Resource hinzu:

```yaml
url: /local/better-dashboard-roles.js
type: module
```

Danach Browser-Cache leeren oder die Home-Assistant App komplett neu starten.

## Konfiguration über die Home-Assistant UI

Nach dem Hinzufügen der Integration kannst du unter `Einstellungen` -> `Geräte & Dienste` -> `Better Dashboard Roles` -> `Konfigurieren` die Gruppen und Dashboard-Rechte verwalten.

Der Options-Dialog bietet zwei Wege:

- `Benutzer einer Gruppe zuweisen`: Home-Assistant-Benutzer auswählen, Gruppe eintragen, speichern.
- `Dashboard fuer Gruppe freigeben`: vorhandenes Dashboard aus Dropdown auswählen, Gruppe eintragen, optional als Standard-Dashboard setzen.
- `Komplette Konfiguration bearbeiten`: Gruppen-, Dashboard- und Default-Dashboard-Konfiguration als YAML-Snippets bearbeiten.

Die UI-Konfiguration wird in Home Assistants `.storage` gespeichert. Du musst für Gruppenzuweisungen nicht mehr `configuration.yaml` bearbeiten.

## Optionale YAML-Konfiguration

YAML kann weiterhin als Basis/Fallback verwendet werden. Wenn du die Integration nur über die UI pflegen willst, kannst du diesen Block weglassen.

In `configuration.yaml`:

```yaml
better_dashboard_roles:
  groups:
    garten:
      users:
        - schwiegervater
        - schwiegermutter
    admins:
      users:
        - daniel

  dashboards:
    lovelace-garten:
      groups:
        - garten
        - admins
    lovelace-wohnung:
      groups:
        - admins
        - wohnung

  default_dashboard:
    garten: lovelace-garten
    admins: lovelace-wohnung
    wohnung: lovelace-wohnung

  options:
    hide_sidebar_items: true
    redirect_blocked_dashboards: true
    hide_admin_menu_for_non_admin: true
    debug: false
```

Nach jeder Änderung an `configuration.yaml` muss Home Assistant neu gestartet werden. Änderungen über `Konfigurieren` werden dagegen über Home Assistant gespeichert und automatisch neu geladen.

## Konfiguration

`groups` ordnet Gruppen eine Liste von Home-Assistant-Benutzern zu. Verwende den angezeigten HA-Benutzernamen oder stabiler die `user_id`, die der API-Endpoint zurückgibt.

`users` ist weiterhin als Legacy-Konfiguration möglich. Dort können einzelne Benutzer direkt eine `role`, `group` oder `groups` bekommen. Für neue Setups ist `groups` übersichtlicher.

`dashboards` definiert, welche Gruppen oder Rollen ein Dashboard sehen dürfen. Die Dashboard-ID entspricht dem URL-Pfad ohne führenden Slash.

Im UI-Dialog `Dashboard fuer Gruppe freigeben` versucht die Integration, die in Home Assistant angelegten Dashboards auszulesen und als Dropdown anzubieten. Das ist bewusst defensiv umgesetzt, weil Home Assistant Dashboard-Daten intern je nach Version anders ablegt. Wenn ein Dashboard dort nicht auftaucht, kannst du es weiterhin in `Komplette Konfiguration bearbeiten` manuell eintragen.

Beispiele:

- `lovelace-garten` entspricht `/lovelace-garten`
- `lovelace-wohnung` entspricht `/lovelace-wohnung`
- `dashboard-garten` entspricht `/dashboard-garten`
- `lovelace` entspricht `/lovelace`

`default_dashboard` definiert das Ziel für Redirects pro Gruppe oder Rolle. Wenn ein Benutzer keine Gruppe und keine Rolle hat, wird automatisch `guest` verwendet. Hat `guest` kein Default-Dashboard, wird nicht redirectet.

## Unterstützte Dashboard-URLs

Das Frontend erkennt unter anderem:

- `/lovelace`
- `/lovelace/default_view`
- `/lovelace-garten`
- `/lovelace-garten/0`
- `/dashboard-garten`
- `/dashboard-garten/view-name`

## API Response

Der Endpoint `GET /api/better_dashboard_roles/config` liefert für den aktuell eingeloggten Benutzer:

```json
{
  "username": "daniel",
  "user_id": "abc123",
  "role": "guest",
  "primary_group": "admins",
  "groups": ["admins"],
  "allowed_dashboards": ["lovelace-garten", "lovelace-wohnung"],
  "default_dashboard": "lovelace-wohnung",
  "default_dashboards": {
    "admins": "lovelace-wohnung"
  },
  "options": {
    "hide_sidebar_items": true,
    "redirect_blocked_dashboards": true,
    "hide_admin_menu_for_non_admin": true,
    "debug": false
  }
}
```

## Troubleshooting

### JS lädt nicht

- Prüfe, ob `better-dashboard-roles.js` unter `config/www/better-dashboard-roles.js` liegt.
- Prüfe die Resource: `/local/better-dashboard-roles.js`, Typ `module`.
- Browser-Cache leeren oder Home-Assistant App komplett beenden und neu öffnen.
- In den Browser-DevTools prüfen, ob die Datei mit HTTP 200 geladen wird.

### Sidebar wird nicht gefiltert

- Prüfe, ob der Endpoint im eingeloggten Browser erreichbar ist: `/api/better_dashboard_roles/config`.
- Setze vorübergehend `debug: true` und prüfe die Browser-Konsole.
- Prüfe, ob die Dashboard-IDs in YAML exakt den URL-Pfaden ohne führenden Slash entsprechen.
- Starte Home Assistant nach YAML-Änderungen neu.

### Benutzername stimmt nicht

- Öffne `/api/better_dashboard_roles/config` im Browser und prüfe `username` und `user_id`.
- Verwende in `users` genau diesen Namen oder alternativ die `user_id` als Schlüssel.
- Home Assistant kann Anzeigenamen anders schreiben als erwartet.

### Dashboard-ID herausfinden

Öffne das Dashboard und schaue auf den ersten URL-Abschnitt nach der Domain:

- `https://homeassistant.local:8123/lovelace-garten/0` -> `lovelace-garten`
- `https://homeassistant.local:8123/dashboard-garten/view-name` -> `dashboard-garten`

## Entwicklung

Es gibt kein Build-System. Die Integration besteht aus:

```text
custom_components/better_dashboard_roles/
www/better-dashboard-roles.js
hacs.json
README.md
example-config.yaml
```

Die Frontend-Datei kann direkt als Lovelace Resource geladen werden.
