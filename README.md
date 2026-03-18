# Seznam škol – interaktivní mapa škol a školských zařízení v ČR

Interaktivní mapa všech škol a školských zařízení v České republice. Zobrazuje mateřské školy,
základní školy, gymnázia, střední školy, základní umělecké školy, vyšší odborné školy, speciální
školy, pedagogicko-psychologické poradny a další zařízení zapsaná v rejstříku MŠMT.

**Živá aplikace:** [tompta1.github.io/skolky-starter](https://tompta1.github.io/skolky-starter/)

---

## Co aplikace umí

- Zobrazí **38 000+ školských pracovišť** na mapě celé České republiky
- Filtruje podle druhu školy (mateřská, základní, gymnázium, střední, ZUŠ, VOŠ, …)
- Ukazuje adresu, datovou schránku, e-mail a webové stránky každé školy
- Při prohlížení automaticky dohledává webové stránky z registru ARES pro školy, které je dosud nemají
- Přímé propojení e-mailem (`mailto:`) i odkazem na web

---

## Zdroje dat a aktuálnost

| Datová sada | Zdroj | Aktualizace |
|-------------|-------|-------------|
| Rejstřík škol a školských zařízení | [MŠMT / LKOD](https://lkod-ftp.msmt.gov.cz/00022985/250d6b3f-71a2-4441-b8a0-4df141071f13/rssz-cela-cr-2026-01-01.jsonld) | Ročně (leden) |
| Datové schránky PO | [Informační systém datových schránek](https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_po) | Průběžně |
| Datové schránky OVM | [ISDS](https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_ovm) | Průběžně |
| Adresní body (souřadnice) | [ČÚZK RÚIAN](https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-ST/RUIAN-CSV-ADR-ST.xml) | Měsíčně |
| Weby škol (doplnění) | [ARES REST API](https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty-rs/{ICO}) | Na vyžádání |

Aktuální dataset byl načten **1. 1. 2026**. Pro aktualizaci spusťte `python -m etl.load refresh` (viz níže).

---

## Architektura

```
frontend/          Vite + React + TypeScript → GitHub Pages
backend/app/       FastAPI REST API → Vercel (serverless)
backend/etl/       ETL pipeline: stažení → parsování → uložení
Neon PostgreSQL    Serverless Postgres (AWS eu-central-1)
```

- **`backend/etl/load.py`** — stáhne zdrojové soubory, přeloží souřadnice z JTSK → WGS84,
  spojí rejstřík škol s adresními body a datovými schránkami, uloží do DB
- **`backend/app/main.py`** — FastAPI: `/api/schools/map`, `/api/schools/nearby`, `/api/schools/enrich`
- **`frontend/src/`** — React mapa (MapLibre GL), boční panel se seznamem, filtry podle druhu školy

### API endpointy

| Endpoint | Popis |
|----------|-------|
| `GET /api/schools/map` | Všechna pracoviště s koordináty (pro mapu) |
| `GET /api/schools/nearby?lat=&lon=&limit=` | Nejbližší školy k danému bodu (Haversinova vzdálenost v SQL) |
| `POST /api/schools/enrich` | Dohledá weby škol z ARES a uloží do DB |

---

## Lokální spuštění

### Požadavky

- Python 3.11+
- Node 20+
- PostgreSQL 14+ (nebo Podman: `podman compose up -d db`)

### Backend

```bash
cd backend
cp .env.example .env          # nastavte DATABASE_URL
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Stažení zdrojů a načtení do DB (trvá ~5 minut)
python -m etl.load refresh

# Spuštění API
uvicorn app.main:app --reload --port 8000
```

Ověření: `curl http://localhost:8000/api/health`

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Pro lokální napojení na lokální backend přidejte do `frontend/.env.local`:

```
VITE_API_BASE=http://localhost:8000
```

### Testy

```bash
cd backend && bin/python -m pytest tests/ -v
cd frontend && npm test
```

---

## Technické poznámky

### Souřadnicový systém

Zdrojová data RÚIAN jsou v S-JTSK (EPSG:5514). ETL pipeline převádí souřadnice do WGS84
(EPSG:4326) pomocí `pyproj` — negace obou os kvůli konvenci ČÚZK (`-Y, -X`).

### Druhy škol

Aplikace zobrazuje všechny druhy škol zapsané v rejstříku MŠMT. Gymnázia jsou v rejstříku
vedena pod kódem `C00` (střední škola) — aplikace je detekuje podle názvu entity a zobrazuje je
jako samostatnou kategorii. Vysoké školy nejsou součástí rejstříku MŠMT a v datech proto chybí.

### ARES enrichment

Při každém posunu mapy aplikace na pozadí (po 2 s prodlevě) pošle až 20 viditelných škol bez
webu na endpoint `/api/schools/enrich`. Ten zavolá ARES REST API pro příslušná IČO, výsledek
uloží do DB a vrátí zpět do frontendu. Každá škola se kontroluje nejvýše jednou (dokud není
zjištěn web nebo prázdný výsledek).

### Datové schránky

Datové schránky jsou párované přes IČO z exportů ISDS. Pro každou právnickou osobu je
preferována datová schránka typu OVM (úřad veřejné moci) před PO (právnická osoba).

### Změna URL rejstříku MŠMT

URL rejstříku MŠMT je v `backend/etl/load.py` jako konstanta `SCHOOL_REGISTRY_URL`. MŠMT
každoročně vydává nový export — při aktualizaci stačí změnit URL a znovu spustit ETL.

---

## Caveats

- **Weby škol:** obohacování z ARES je na principu best-effort; soukromé školy (s.r.o., a.s.)
  mají výrazně vyšší pokrytí než příspěvkové organizace.
- **Gymnázia:** záznamy v rejstříku nesou `school_kind_code = C00`; detekce podle `entity_name`
  zachytí drtivou většinu, ale ne všechna gymnázia (záleží na přesném znění názvu).
- **Koordináty:** menší část pracovišť nemá přiřazený adresní bod RÚIAN — tato pracoviště se
  na mapě nezobrazí.
