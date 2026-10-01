# openHAB Google Bridge

Verbindet **openHAB** mit **Gmail** und **Google Calendar** über die Google API.
Steuere dein Smart Home per E-Mail und führe zeitgesteuerte Commands über Kalendertermine aus.

---

## Inhaltsverzeichnis

1. [Gmail-Konto anlegen](#1-gmail-konto-anlegen)
2. [Google Cloud Project erstellen](#2-google-cloud-project-erstellen)
3. [credentials.json herunterladen](#3-credentialsjson-herunterladen)
4. [Bridge installieren](#4-bridge-installieren)
5. [Bridge konfigurieren](#5-bridge-konfigurieren)
6. [OAuth2 einrichten (einmalig)](#6-oauth2-einrichten-einmalig)
7. [Bridge starten](#7-bridge-starten)
8. [Als Systemdienst einrichten](#8-als-systemdienst-einrichten-linux)
9. [E-Mail-Nutzung](#9-e-mail-nutzung)
10. [Kalender-Nutzung](#10-kalender-nutzung)

---

## 1. Gmail-Konto anlegen

1. Gehe zu **https://accounts.google.com/signup**
2. Wähle: „Für mich selbst" → E-Mail-Adresse wählen (z. B. `smarthome.openhab@gmail.com`)
3. Kein Telefon nötig – du kannst die Handynummer-Eingabe überspringen
4. Konto vollständig einrichten

---

## 2. Google Cloud Project erstellen

> Kein Azure, keine Kreditkarte – nur ein Google-Konto ist nötig.

### 2.1 Google Cloud Console öffnen

1. Gehe zu **https://console.cloud.google.com/**
2. Melde dich mit dem eben erstellten Gmail-Konto an
3. Stimme den Nutzungsbedingungen zu (kein Geld nötig)

### 2.2 Neues Projekt anlegen

1. Oben links auf **„Projekt auswählen"** klicken
2. **„Neues Projekt"** klicken
3. Name: `openhab-google-bridge`
4. **„Erstellen"** klicken, dann das Projekt auswählen

### 2.3 Gmail API aktivieren

1. Linkes Menü: **„APIs & Dienste" → „Bibliothek"**
2. Nach **„Gmail API"** suchen → **„Aktivieren"**

### 2.4 Google Calendar API aktivieren

1. Wieder in der Bibliothek
2. Nach **„Google Calendar API"** suchen → **„Aktivieren"**

### 2.5 OAuth-Zustimmungsbildschirm konfigurieren

1. Linkes Menü: **„APIs & Dienste" → „OAuth-Zustimmungsbildschirm"**
2. Benutzertyp: **„Extern"** → **„Erstellen"**
3. Pflichtfelder ausfüllen:
   - **App-Name:** `openHAB Google Bridge`
   - **Supportmailadresse:** deine Gmail-Adresse
   - **E-Mail-Adressen für Entwicklerkontakt:** deine Gmail-Adresse
4. **„Speichern und fortfahren"**
5. Seite „Bereiche": **„Speichern und fortfahren"** (Bereiche werden dynamisch angefragt)
6. Seite „Testnutzer": **„+ ADD USERS"** → deine Gmail-Adresse eintragen → **„Speichern und fortfahren"**
7. Zusammenfassung: **„Zurück zum Dashboard"**

> **Wichtig:** Die App bleibt im „Testing"-Modus. Das ist für den Eigenbetrieb
> vollkommen ausreichend. Es wird **keine Verifizierung** benötigt.

### 2.6 OAuth-Client-ID erstellen

1. Linkes Menü: **„APIs & Dienste" → „Anmeldedaten"**
2. **„+ Anmeldedaten erstellen" → „OAuth-Client-ID"**
3. Anwendungstyp: **„Desktop-App"**
4. Name: `openhab-bridge-client`
5. **„Erstellen"**
6. Im Dialog: **„JSON herunterladen"** klicken
7. Die heruntergeladene Datei als **`credentials.json`** im Projektverzeichnis speichern

---

## 3. credentials.json herunterladen

Die im vorherigen Schritt heruntergeladene Datei muss als `credentials.json`
direkt im Projektverzeichnis liegen:

```
openhab-google-bridge/
├── credentials.json      ← hier ablegen
├── main.py
├── ...
```

---

## 4. Bridge installieren

```bash
# Projektverzeichnis betreten
cd openhab-google-bridge

# Abhängigkeiten installieren
pip install -r requirements.txt
```

---

## 5. Bridge konfigurieren

```bash
cp .env.example .env
nano .env
```

Folgende Werte anpassen:

```ini
# openHAB
OPENHAB_URL=http://localhost:8080
OPENHAB_TOKEN=               # Optional: API-Token aus openHAB-Einstellungen
OPENHAB_USER=                # Optional: Basic Auth
OPENHAB_PASS=                # Optional: Basic Auth

# Sicherheitsschlüssel – UNBEDINGT ÄNDERN!
BRIDGE_SECRET_KEY=MeinSicheresPasswort456

# Verhalten (optional anpassen)
SSE_TIMEOUT_SECONDS=15
POLL_INTERVAL_SECONDS=60
CALENDAR_POLL_INTERVAL_SECONDS=120
```

---

## 6. OAuth2 einrichten (einmalig)

```bash
python auth_setup.py
```

- Ein Browser-Fenster öffnet sich
- Mit dem Gmail-Konto anmelden
- Google zeigt eine Warnung **„Diese App wurde nicht verifiziert"**
  → **„Erweitert"** klicken → **„Zu openHAB Google Bridge (unsicher)"** klicken
- Alle Berechtigungen erteilen (Gmail lesen/senden, Kalender verwalten)
- Das Token wird als `google_token.json` gespeichert

Das Token wird automatisch erneuert (Refresh Token). Es muss nicht wiederholt werden.

---

## 7. Bridge starten

```bash
python main.py
```

---

## 8. Als Systemdienst einrichten (Linux)

```bash
sudo nano /etc/systemd/system/openhab-google-bridge.service
```

```ini
[Unit]
Description=openHAB Google Bridge
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/openhab-google-bridge
ExecStart=/usr/bin/python3 /home/pi/openhab-google-bridge/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable openhab-google-bridge
sudo systemctl start openhab-google-bridge
sudo systemctl status openhab-google-bridge
```

---

## 9. E-Mail-Nutzung

### Body-Format (für ALLE E-Mails)

```
Zeile 1: Command oder leer (bei reinen Abfragen)
Zeile 2: BRIDGE_SECRET_KEY
```

### Unterstützte Betreff-Präfixe

| Betreff | Beschreibung |
|---|---|
| `CMD: testSwitch` | Command an Item senden |
| `cmd: testSwitch` | (Kleinschreibung auch ok) |
| `Command: testSwitch` | (Langform auch ok) |
| `State: testSwitch` | State eines Items abfragen |
| `STATE: testSwitch` | (Großschreibung auch ok) |
| `ITEM: testSwitch` | Vollständiger JSON-Response |
| `GET: Items` | Alle Items auflisten |
| `GET: Rules` | Alle Rules auflisten |
| `GET: Things` | Alle Things auflisten |
| `GET: Sitemaps` | Alle Sitemaps auflisten |

| `GET CALENDAR: today` | Heutige Termine |
| `GET CALENDAR: tomorrow` | Morgige Termine |
| `GET CALENDAR: next_hour` | Termine in der nächsten Stunde |
| `GET CALENDAR: week` | Termine der nächsten 7 Tage |
| `GET CALENDAR: accepted` | Erfolgreich ausgeführte Termine |
| `GET CALENDAR: declined` | Fehlgeschlagene Termine |
| `GET CALENDAR: all` | Alle zukünftigen Termine |

### Beispiel: Switch einschalten

- **An:** `smarthome.openhab@gmail.com`
- **Betreff:** `CMD: wohnzimmerLicht`
- **Body:**
  ```
  ON
  MeinSicheresPasswort456
  ```

### Beispiel: State abfragen

- **Betreff:** `State: aussentemperatur`
- **Body:**
  ```
  
  MeinSicheresPasswort456
  ```

---

## 10. Kalender-Nutzung

### Termin anlegen (Google Calendar)

1. **https://calendar.google.com** öffnen
2. Neuen Termin erstellen:
   - **Titel:** `CMD: wohnzimmerLicht`
   - **Datum/Uhrzeit:** gewünschter Ausführungszeitpunkt
   - **Beschreibung:**
     ```
     ON
     MeinSicheresPasswort456
     ```
3. Termin speichern

### Was passiert dann?

| Situation | Google-Kalender-Farbe |
|---|---|
| Erfolgreich ausgeführt | 🟢 Grün (SAGE) = Zusage |
| Fehler / Key falsch / Item nicht gefunden | 🔴 Rot (TOMATO) = Absage |
| Noch nicht verarbeitet | Standardfarbe = Ausstehend |

- Bereits verarbeitete Termine (grün/rot) werden **nicht erneut ausgeführt**
- Gelöschte Termine werden übersprungen
- Der Status + Zeitstempel wird automatisch in die Terminbeschreibung geschrieben

---

## Projektstruktur

```
openhab-google-bridge/
├── main.py                    # Einstiegspunkt
├── auth_setup.py              # Einmalige OAuth2-Authentifizierung
├── requirements.txt
├── .env.example
├── .env                       # Deine Konfiguration (nicht einchecken!)
├── credentials.json           # Google OAuth-Credentials (nicht einchecken!)
├── google_token.json          # Wird automatisch erstellt (nicht einchecken!)
├── config/
│   └── settings.py
└── modules/
    ├── google_auth.py         # OAuth2-Token-Verwaltung
    ├── gmail_handler.py       # E-Mail empfangen & verarbeiten
    ├── gmail_sender.py        # E-Mail versenden
    ├── calendar_handler.py    # Kalendertermine ausführen & abfragen
    ├── openhab_client.py      # openHAB REST API Wrapper
    └── security.py            # Schlüssel-Validierung
```
