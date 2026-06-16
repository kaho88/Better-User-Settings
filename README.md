# Better User Settings

Better User Settings ist eine HACS-kompatible Home-Assistant Custom Integration fuer globale Dashboard-Sichtbarkeit in der Sidebar.

Die Integration speichert Gruppen und Dashboard-Regeln in Home Assistants `.storage`, prueft Benutzer ueber die stabile Home-Assistant `user_id` und laedt ein globales Frontend-Script. Das Script wird nicht als Lovelace-Resource pro Dashboard eingebunden.

## Sicherheitshinweis

Das ist keine harte Zugriffskontrolle.

Die Integration versteckt Dashboard-Links in der Home-Assistant-Oberflaeche und kann blockierte Dashboard-URLs umleiten. Home-Assistant-APIs, Entitaeten und Views bleiben technisch erreichbar, wenn Home Assistant selbst sie erlaubt.

## Funktionen

- Admin-Panel unter `/better-user-settings`
- Gruppenverwaltung mit Dropdown und Mehrfachauswahl von Home-Assistant-Benutzern
- Speicherung von `user_id`, Anzeigenamen nur fuer die UI
- Dashboard-Erkennung aus Home Assistant inklusive `lovelace_dashboards` Storage
- Dashboard-Regeln mit mehreren erlaubten Gruppen pro Dashboard
- Frei konfigurierbare Sidebar-Regeln fuer Eintraege wie Karte, Aktivitaet, Verlauf oder Energie
- Persistenz ueber Home Assistant `.storage`
- WebSocket-API fuer Admin-UI und aktuelle User-Permissions
- Globales Sidebar-Script mit `MutationObserver`
- Admins sehen immer alle Dashboards
- Nicht konfigurierte Dashboards bleiben fuer normale Benutzer sichtbar

## Installation

1. Repository ueber HACS als Integration installieren.
2. Home Assistant neu starten.
3. Unter `Einstellungen` -> `Geraete & Dienste` die Integration `Better User Settings` hinzufuegen.
4. Danach erscheint fuer Admins der Sidebar-Eintrag `User Settings`.

Hinweis zur Umbenennung: Der technische Domain-Name ist `better_user_settings`. Bestehende `.storage`-Daten aus `better_dashboard_roles` werden beim ersten Start uebernommen. Ein alter Home-Assistant-Config-Entry unter dem frueheren Domain-Namen muss nach der Umbenennung einmal entfernt und als `Better User Settings` neu hinzugefuegt werden.

Das globale Frontend-Script wird von der Integration registriert. Falls eine Home-Assistant-Version diese interne Registrierung nicht erlaubt, steht im Log ein Fallback-Hinweis. Dann kann man manuell ergaenzen:

```yaml
frontend:
  extra_module_url:
    - /better_user_settings_static/better-user-settings.js
```

## Admin-UI

Im Panel `User Settings` gibt es drei Tabs:

- `Gruppen`: Gruppe auswaehlen oder neue Gruppen-ID eintragen, Namen setzen, Benutzer per Mehrfachauswahl zuordnen.
- `Dashboards`: Dashboard auswaehlen, erlaubte Gruppen per Mehrfachauswahl setzen, vorhandene Regeln in der Tabelle pruefen.
- `Sidebar`: Nicht-Dashboard-Eintrag wie `/map` oder `/logbook` auswaehlen, eigene Pfade eintragen und erlaubte Gruppen setzen.

Intern werden nur IDs gespeichert:

```yaml
groups:
  group_id:
    name: Garten
    users:
      - user_id_1
      - user_id_2

dashboards:
  /dashboard-garten:
    allowed_groups:
      - group_id

sidebar_items:
  /map:
    allowed_groups:
      - group_id
```

## Verhalten

- Admins sehen alle Dashboard-Eintraege.
- Normale Benutzer sehen Dashboards ohne Regel und Dashboards, deren `allowed_groups` eine ihrer Gruppen enthaelt.
- Normale Benutzer sehen konfigurierte Sidebar-Eintraege wie `/map` oder `/logbook` nur, wenn ihre Gruppe erlaubt ist.
- Benutzer ohne Gruppe sehen nur Dashboards ohne Einschraenkung.
- Nicht konfigurierte Nicht-Dashboard-Menuepunkte werden vom Sidebar-Filter nicht veraendert.
- Die Sidebar wird nach Render, Navigation und dynamischen Aenderungen erneut gefiltert.

## API

HTTP fuer das globale Frontend:

- `GET /api/better_user_settings/permissions`
- `GET /api/better_user_settings/config` als Legacy-kompatibler Alias

WebSocket-Kommandos:

- `better_user_settings/get_groups`
- `better_user_settings/save_group_users`
- `better_user_settings/get_dashboards`
- `better_user_settings/save_dashboard_allowed_groups`
- `better_user_settings/get_sidebar_items`
- `better_user_settings/save_sidebar_item_allowed_groups`
- `better_user_settings/get_permissions`
- `better_user_settings/get_allowed_paths`

Admin-Schreibzugriffe sind serverseitig auf Home-Assistant-Admins beschraenkt.

## Optionale YAML-Basis

YAML kann als Erst-Migration oder Fallback genutzt werden. Neue Admin-Aenderungen werden in `.storage` gespeichert.

```yaml
better_user_settings:
  groups:
    garten:
      users:
        - home_assistant_user_id

  dashboards:
    /dashboard-garten:
      groups:
        - garten

  sidebar_items:
    /map:
      groups:
        - garten
    /logbook:
      groups:
        - admins

  options:
    hide_sidebar_items: true
    redirect_blocked_dashboards: true
    debug: false
```

Bei der Migration versucht die Integration, alte Benutzernamen auf aktuelle Home-Assistant-User-IDs abzubilden. Neue Regeln sollten direkt ueber das Admin-Panel gepflegt werden.
