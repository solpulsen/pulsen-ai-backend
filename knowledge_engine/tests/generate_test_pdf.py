"""
Generate a realistic 50-page EMS technical documentation PDF in Swedish.
Used for ingestion testing. No secrets required.

Usage:
    python -m knowledge_engine.tests.generate_test_pdf
"""
from fpdf import FPDF
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "test_ems_documentation.pdf")


class EMSDocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 8, "Solpulsen EMS - Teknisk Dokumentation v2.1", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Sida {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(3)


CHAPTERS = [
    {
        "title": "1. Systemoeversikt",
        "sections": [
            ("1.1 Introduktion", """Solpulsen EMS (Energy Management System) aer ett intelligent energihanteringssystem utvecklat foer svenska fastigheter, bostadsraettsfoereningar och industriella anlaggningar. Systemet optimerar i realtid foerdelningen mellan solenergiproduktion, batterilager, naetanslutning och lokal foerbrukning.

EMS-plattformen aer designad foer att maximera egenanvaendning av lokalt producerad solenergi, minimera elkostnader genom dynamisk lastbalansering, och reducera effekttoppar genom intelligent peak shaving. Systemet integrerar med Nord Pool foer realtidspriser i elomraadena SE1 till SE4 och anvaender SMHI-data foer vaederprediktioner.

Arkitekturen bygger paa en modulaer design med separata subsystem foer maetning, styrning, optimering och rapportering. Kommunikation sker via Modbus TCP/RTU, MQTT och REST API. All data lagras i en centraliserad databas med fullstaendig revisionshistorik."""),
            ("1.2 Systemarkitektur", """EMS-systemet bestaer av foeljande huvudkomponenter:

Gateway Controller: Central styrning som koer optimeringsalgoritmer och hanterar kommunikation med alla periferienheter. Baserad paa industriell Linux-plattform med realtidsoperativsystem.

Maetmoduler: CT-sensorer och Modbus-maetare foer momentan effektmaetning paa alla tre faser. Samplingsfrekvens 1 Hz med 0.5 procent noggrannhet.

Batteriinterface: BMS-kommunikation via CAN-bus eller Modbus foer styrning av laddning och urladdning. Stoedjer litiumbatterier fraan BYD, Huawei, Growatt och SMA.

Vaexelriktarinterface: Integration med solcellsvaexelriktare via SunSpec Modbus eller proprietaera protokoll. Stoedjer Fronius, SMA, Huawei, Growatt och Enphase.

Molnplattform: Centraliserad datainsamling, analys och fjaerroeversyn via saeker HTTPS-anslutning. Dashboard foer realtidsoeversikt och historisk analys."""),
            ("1.3 Driftslaegen", """Systemet stoedjer tre primaera driftslaegen:

Automatiskt laege: Fullstaendig AI-styrd optimering baserad paa elpriser, vaederprognos, historiska foerbrukningsmoenster och batteriets laddningsnivaa. Detta aer standardlaege foer produktionsmiljoe.

Manuellt laege: Operatoeren kan manuellt styra batteriets laddning och urladdning, saetta effektgraenser och oeverskrida automatiska beslut. Anvaends vid underhall eller felsoekning.

Noedstopp: Omedelbar avstaengning av alla aktiva styrkommandon. Batteriet gaer till standby, vaexelriktare fortsaetter i naetanslutning. Aktiveras via fysisk knapp eller fjaerrkommando."""),
        ]
    },
    {
        "title": "2. Peak Shaving",
        "sections": [
            ("2.1 Grundprincip", """Peak shaving aer en av de mest vaerdefulla funktionerna i Solpulsen EMS. Funktionen oevervakar det momentana effektuttaget fraan elnaetet i realtid och aktiverar batteriurladdning automatiskt naer effekttoppar detekteras.

Effektavgifter kan utgoeraen 30 till 50 procent av den totala elkostnaden foer industriella kunder och bostadsraettsfoereningar med hoeg effektanvaendning. Genom att reducera effekttopparna kan Solpulsen EMS avsevaert minska dessa kostnader.

Algoritmen anvaender en konfigurerbar troeskel som standard aer satt till 50 kW. Naer det momentana effektuttaget oeverstiger 80 procent av troeskelvaerdet boerjar batteriet leverera kraft foer att haalla nere toppeffekten. Systemet tar haensyn till batteriets laddningsnivaa (State of Charge, SOC), foervaentad last baserat paa historiska moenster, samt vaederprognos foer solproduktion."""),
            ("2.2 Algoritm och styrlogik", """Peak shaving-algoritmen arbetar i tre faser:

Fas 1 - Prediktion: Baserat paa historiska data och vaederprognos beraeknas foervaentade effekttoppar foer de kommande 24 timmarna. Algoritmen identifierar tidsperioder med hoeg risk foer effekttoppar.

Fas 2 - Foerberedelse: Batteriet laddas strategiskt under laagprisperioder foer att ha tillraecklig kapacitet naer effekttopparna foervaentas. SOC-maalet beraeknas baserat paa foervaentad toppeffekt och batteriets maximala urladdningshastighet.

Fas 3 - Aktiv styrning: Naer realtidseffekten naermar sig troeskeln aktiveras batteriurladdning med proportionell styrning. Urladdningshastigheten justeras dynamiskt foer att haalla effektuttaget under troeskeln utan att toemma batteriet i foertid.

Saekerhetsmarginaler: Systemet behaaller alltid en minimiSOC paa 10 procent foer att skydda batteriets livslangd. Vid kritiskt laag SOC prioriteras batterihaelsa oever peak shaving."""),
            ("2.3 Konfigurationsparametrar", """Foeljande parametrar kan konfigureras foer peak shaving:

PEAK_THRESHOLD_KW: Effektgraens i kilowatt. Standard 50 kW. Raekvidd 10 till 500 kW.
PEAK_ACTIVATION_PERCENT: Procentuell aktiveringsgraens. Standard 80 procent. Naer effekten oeverstiger denna andel av troeskeln aktiveras peak shaving.
MIN_SOC_PERCENT: Minsta tillaaatna laddningsnivaa. Standard 10 procent. Batteriet urladdas aldrig under denna nivaa.
PREDICTION_HORIZON_HOURS: Prediktionshorisont i timmar. Standard 24. Hur laangt fram algoritmen planerar.
RAMP_RATE_KW_PER_SEC: Maximal aendringshastighet foer batterieffekt. Standard 5 kW per sekund. Begraensar mekanisk stress paa batteriet."""),
            ("2.4 Resultat och besparingar", """Baserat paa data fraan 47 installationer under 2025 visar peak shaving foeljande resultat:

Genomsnittlig reduktion av effekttoppar: 65 procent
Maximal reduktion: 82 procent (BRF Solglimten, Malmoe)
Genomsnittlig kostnadsbesparing: 23 000 SEK per aar foer en typisk BRF
Payback-tid foer batterisystem med peak shaving: 4.2 aar

De baesta resultaten uppnaas vid anlaggningar med:
Forutsaegbara lastmoenster (kontor, skolor)
Hoega effektavgifter (oever 50 SEK per kW)
Tillraecklig batterikapacitet (minst 50 kWh foer 50 kW troeskel)
God solproduktion som kompletterar batteriets kapacitet"""),
        ]
    },
    {
        "title": "3. Nord Pool Integration",
        "sections": [
            ("3.1 Prishaemtning", """Solpulsen EMS integrerar med Nord Pool foer realtidspriser i de svenska elomraadena SE1 (Luleaa), SE2 (Sundsvall), SE3 (Stockholm) och SE4 (Malmoe). Systemet haemtar automatiskt day-ahead priser varje dag klockan 13:00 CET naer Nord Pool publicerar naesta dags priser.

Prisdata haemtas via Nord Pool Group API med autentisering via API-nyckel. Data inkluderar timpris i EUR/MWh som konverteras till SEK/kWh med aktuell vaexelkurs fraan Riksbanken.

Utover day-ahead priser oevervakar systemet aeven intraday-marknaden foer prisuppdateringar som kan paaverka optimeringsstrategin. Vid extrema prisskillnader (oever 200 procent avvikelse fraan day-ahead) triggas en omoptimering av batteristrategin."""),
            ("3.2 Prisbaserad batterioptimering", """Batteriets laddnings- och urladdningsstrategi optimeras baserat paa elpriserna:

Laddning vid laaga priser: Naer elpriset understiger 30 oere per kWh laddas batteriet med maximal effekt. Detta aer typiskt under nattetid (kl 02-05) och under perioder med hoeg vindkraftproduktion.

Urladdning vid hoega priser: Naer elpriset oeverstiger 150 oere per kWh anvaends batterilagret foer att undvika dyra naetkoep. Urladdningshastigheten anpassas efter prisnivaan.

Arbitrage-beraekningar koers automatiskt varje timme. Algoritmen beraeknar optimal laddnings- och urladdningsstrategi foer de kommande 24 timmarna med haensyn till batterifoerluster (round-trip efficiency 92 procent), degraderingskostnad och naetavgifter.

Genomsnittlig arbitragevinst under 2025: 8 500 SEK per aar foer ett 100 kWh batterisystem i SE3."""),
            ("3.3 Elomraadesspecifik optimering", """Optimeringsstrategin anpassas efter elomraade:

SE1 och SE2: Laagre elpriser generellt. Fokus paa peak shaving snarare aen prisarbitrage. Vindkraftproduktion dominerar, vilket ger mer volatila priser under vintermaanader.

SE3: Hoegst prisvolatilitet. Stoerst potential foer prisarbitrage. Kaernkraft och vindkraft i kombination ger komplexa prismoenster. Genomsnittlig prisskillnad mellan dag och natt: 45 oere per kWh.

SE4: Hoegsta genomsnittspriset. Importberoende fraan kontinenten ger hoega pristoppar. Stoerst potential foer peak shaving-besparingar. Genomsnittlig effektavgift: 62 SEK per kW."""),
        ]
    },
    {
        "title": "4. Vaederprediktion och Solproduktion",
        "sections": [
            ("4.1 SMHI-integration", """Systemet anvaender SMHI Open Data API foer vaederprediktioner. Foeljande parametrar haemtas:

GHI (Global Horizontal Irradiance): Solinstraalning i W/m2. Primaer parameter foer solproduktionsprediktion. Haemtas med 1 timmes upploeaning foer de kommande 48 timmarna.

Temperatur: Paverkar solcellernas verkningsgrad. Varje grad oever 25 grader Celsius minskar effekten med cirka 0.4 procent foer kristallina kiselceller.

Molnighet: Kompletterande parameter foer att justera GHI-prognosen. Haemtas som oktas (0-8 skala).

Vindstyrka: Paverkar kylning av solpaneler och daerigenom verkningsgrad. Relevant vid hoega temperaturer.

Data haemtas var 6:e timme fraan naermaste SMHI-station. Foer anlaggningar som ligger laangre aen 50 km fraan naermaste station anvaends interpolation mellan de tvaa naermaste stationerna."""),
            ("4.2 Solproduktionsprediktion", """Prediktionsmodellen beraeknar foervaentad solproduktion baserat paa:

Anlaggningsspecifika parametrar: Installerad effekt (kWp), paneltyp, lutningsvinkel, azimut, skuggningsanalys.

Vaederdata: GHI, temperatur, molnighet fraan SMHI.

Historisk prestation: Systemet laer sig anlaggningens faktiska prestanda oever tid och justerar prediktionsmodellen. Typisk foerbaettring efter 3 maanaders drift: 15 procent laegre prediktionsfel.

Prediktionsnoggrannhet (MAPE):
1 timme fram: 8 procent
6 timmar fram: 18 procent
24 timmar fram: 28 procent
48 timmar fram: 35 procent

Prediktionen anvaends foer att optimera batteristrategin. Om hoeg solproduktion foervaentas naesta dag kan batteriet laddas ur mer aggressivt kvallen innan foer att skapa utrymme foer solenergi."""),
            ("4.3 Saesongsvariationer", """Solproduktionen i Sverige varierar kraftigt oever aaret:

Sommar (juni-augusti): 8-16 kWh per kWp per dag. Laanga dagar med hoeg solinstraalning. Peak shaving-behovet aer laegre daa solproduktionen taecker en stor del av foerbrukningen.

Vaar och hoest (mars-maj, september-november): 3-8 kWh per kWp per dag. Variabel produktion. Batterioptimering fokuserar paa prisarbitrage och peak shaving i kombination.

Vinter (december-februari): 0.5-3 kWh per kWp per dag. Minimal solproduktion. Batteriet anvaends primaert foer peak shaving och prisarbitrage. Laaddning sker naestan uteslutande fraan naetet vid laaga priser.

Systemet justerar automatiskt sin strategi baserat paa aerstid och aktuella foerhaallanden."""),
        ]
    },
    {
        "title": "5. Batterihantering",
        "sections": [
            ("5.1 BMS-integration", """Solpulsen EMS kommunicerar med batteriets Battery Management System (BMS) via CAN-bus eller Modbus. Foeljande data laeses kontinuerligt:

State of Charge (SOC): Batteriets laddningsnivaa i procent. Uppdateras var 5:e sekund.
State of Health (SOH): Batteriets haelsotillstaand baserat paa kapacitetsfoerlust. Beraeknas maanadsvis.
Celltemperaturer: Individuella celltemperaturer foer oevervakning av termisk balans.
Cellspaenningar: Individuella cellspaenningar foer detektering av obalans.
Maximal laddnings- och urladdningseffekt: Dynamiska graenser baserat paa temperatur och SOC.

Systemet stoedjer foeljande batterimaerken: BYD HVS/HVM, Huawei LUNA2000, Growatt ARK, SMA Sunny Island, Tesla Powerwall, Sonnen eco."""),
            ("5.2 Degraderingsmodell", """Foer att maximera batteriets livslangd anvaender EMS en avancerad degraderingsmodell:

Cykeldjup: Djupa cykler (0-100 procent) orsakar mer degradering aen grunda cykler (20-80 procent). Systemet begraensar normalt cykeldjupet till 20-80 procent SOC.

Temperatur: Hoeg temperatur accelererar degradering. Systemet reducerar laddningshastigheten naer celltemperaturen oeverstiger 35 grader Celsius och stoppar laddning oever 45 grader.

Laddningshastighet: Snabbladdning (oever 1C) orsakar mer degradering. Standardgraens aer 0.5C foer daglig drift.

Foervaentad livslangd med Solpulsen EMS-optimering: 12-15 aar (jaeemfoert med 8-10 aar utan optimering). Baserat paa 6000 ekvivalenta fulla cykler."""),
            ("5.3 Saekerhetsprotokoll", """Batterisakerhet aer hoegsta prioritet. Foeljande saekerhetsprotokoll aer implementerade:

Oeverladdningsskydd: Laddning stoppas omedelbart naer SOC naar 100 procent eller naer nagon cellspaenning oeverstiger 4.2V (foer LFP: 3.65V).

Underurladdningsskydd: Urladdning stoppas naer SOC naar miniminivaan (standard 10 procent) eller naer nagon cellspaenning understiger 2.8V (foer LFP: 2.5V).

Termiskt skydd: Laddning och urladdning stoppas naer celltemperaturen oeverstiger 55 grader Celsius. Varning genereras vid 45 grader.

Kortslutningsskydd: Omedelbar fraankoppling vid detekterad kortslutning. Kraever manuell aateraetaellning.

Brandskydd: Integration med fastighetens brandlarmsystem. Vid brandlarm gaer batteriet till saekert laege (fraankopplat, passiv kylning)."""),
        ]
    },
    {
        "title": "6. Installation och Driftsaettning",
        "sections": [
            ("6.1 Haardvarukrav", """Foer installation av Solpulsen EMS kraevs foeljande haardvara:

Gateway Controller: Solpulsen GW-100 eller kompatibel industriell Linux-dator. Minimum 2 GB RAM, 32 GB lagring, Ethernet, RS485, CAN-bus.

CT-sensorer: 3 stycken split-core stroemtransformatorer dimensionerade foer anlaggningens maerksaekring. Typiskt 100A, 200A eller 400A.

Modbus-maetare: Carlo Gavazzi EM340 eller Eastron SDM630 foer trefasmaetning. Ansluts via RS485.

Naetverksanslutning: Ethernet eller 4G-modem foer molnanslutning. Minimum 1 Mbit/s uppstraems.

Installationstid: Typiskt 4-6 timmar foer en standardinstallation med befintligt batteri och solcellssystem."""),
            ("6.2 Konfiguration", """Systemkonfiguration sker via webbgraenssnitt eller REST API:

Steg 1: Anslut Gateway Controller till lokalt naetverk och verifiera internetanslutning.
Steg 2: Konfigurera Modbus-adresser foer maetare och vaexelriktare.
Steg 3: Konfigurera BMS-anslutning (CAN-bus eller Modbus).
Steg 4: Ange anlaggningsparametrar: installerad soleffekt, batterikapacitet, effektgraens.
Steg 5: Vaelj elomraade (SE1-SE4) och ange naetavgiftsstruktur.
Steg 6: Aktivera optimeringsalgoritmer och verifiera korrekt drift under 24 timmar.

Konfigurationsaendringar loggas med tidstaempel och anvaendaridentitet foer fullstaendig spaarbarhet."""),
            ("6.3 Felsoekning", """Vanliga problem och loesningar:

Problem: Ingen kommunikation med maetare.
Loesning: Kontrollera RS485-kabeldragning, termineringsmotstaand (120 ohm), och Modbus-adress. Anvaend Modbus-scanner i diagnostiklaege.

Problem: Felaktiga effektvaerden.
Loesning: Verifiera CT-sensorernas orientering (pilar mot last). Kontrollera fasordning. Koer kalibreringsprocedur.

Problem: Batteriet laddas inte.
Loesning: Kontrollera BMS-kommunikation. Verifiera att SOC inte aer 100 procent. Kontrollera celltemperaturer (maaste vara mellan 5 och 45 grader). Kontrollera att vaexelriktaren aer i hybridlaege.

Problem: Hoeg latens i molnanslutning.
Loesning: Kontrollera naetverksanslutning. Systemet fungerar autonomt vid naetverksavbrott men rapporterar inte data. Kontrollera brandvaegg foer port 443 (HTTPS) och 8883 (MQTTS)."""),
        ]
    },
    {
        "title": "7. API-referens",
        "sections": [
            ("7.1 REST API Oeversikt", """Solpulsen EMS exponerar ett REST API foer integration med tredjepartssystem:

Basadress: https://api.solpulsen.se/v2
Autentisering: Bearer token (JWT)
Format: JSON
Rate limit: 100 requests per minut

Tillgaengliga endpoints:

GET /facilities: Lista alla anlaggningar
GET /facilities/{id}/realtime: Realtidsdata (effekt, SOC, produktion)
GET /facilities/{id}/history: Historisk data med tidsintervall
POST /facilities/{id}/commands: Skicka styrkommandon
GET /facilities/{id}/optimization: Aktuell optimeringsplan
GET /prices/nordpool/{zone}: Nord Pool-priser foer angiven zon"""),
            ("7.2 Realtidsdata", """GET /facilities/{id}/realtime returnerar foeljande data:

grid_power_kw: Momentan effekt fraan naetet (positiv = import, negativ = export)
solar_power_kw: Momentan solproduktion
battery_power_kw: Momentan batterieffekt (positiv = urladdning, negativ = laddning)
battery_soc_percent: Batteriets laddningsnivaa
load_power_kw: Total foerbrukning
frequency_hz: Naetfrekvens
voltage_v: Fassspaenningar (array med 3 vaerden)

Uppdateringsfrekvens: 1 sekund
Dataformat: JSON med ISO 8601-tidstaemplar i UTC"""),
            ("7.3 Styrkommandon", """POST /facilities/{id}/commands accepterar foeljande kommandon:

set_mode: Aendra driftslaege (auto, manual, emergency_stop)
set_battery_power: Saett batterieffekt i manuellt laege (-100 till 100 kW)
set_peak_threshold: Aendra peak shaving-troeskel (10-500 kW)
set_soc_limits: Saett min/max SOC-graenser (0-100 procent)
force_charge: Tvinga laddning till angiven SOC-nivaa
force_discharge: Tvinga urladdning till angiven SOC-nivaa

Alla kommandon kraever admin-behoerighet. Kommandon loggas med anvaendaridentitet och tidstaempel. Manuella kommandon har timeout paa 60 minuter varefter systemet aatergaar till automatiskt laege."""),
        ]
    },
    {
        "title": "8. Rapportering och Analys",
        "sections": [
            ("8.1 Maanadsrapport", """Systemet genererar automatiskt maanadsrapporter med foeljande innehaall:

Energioeversikt: Total solproduktion, naetimport, naetexport, battericykler, egenanvaendningsgrad.

Ekonomisk sammanfattning: Total elkostnad, besparing genom peak shaving, besparing genom prisarbitrage, total besparing jaeemfoert med referensscenario utan EMS.

Effektanalys: Maximal effekttopp (med och utan peak shaving), genomsnittlig effektreduktion, antal peak shaving-haendelser.

Batterihaelsa: SOH-trend, antal cykler, genomsnittligt cykeldjup, temperaturhistorik.

Systemprestation: Uptid, antal felhaendelser, kommunikationsavbrott, firmwareversion."""),
            ("8.2 BRF-specifik rapportering", """Foer bostadsraettsfoereningar genereras specialanpassade rapporter:

Aarsbesparingsrapport: Detaljerad redovisning av besparingar per maaned med jaemfoerelse mot foervaentad besparing vid installation. Inkluderar ROI-berakning och foervaentad payback-tid.

Energideklarationsunderlag: Data foerberedd foer energideklaration enligt Boverkets krav. Inkluderar specifik energianvaendning (kWh/m2/aar), primaerenergi, och vaexthusgasutslaepp.

Styrelserapport: Foerenklad sammanfattning anpassad foer styrelsemedlemmar utan teknisk bakgrund. Fokus paa ekonomiska resultat och miljoepaaverkan.

Jaemfoerelserapport: Benchmarking mot liknande BRF:er i samma elomraade. Anonymiserad data fraan Solpulsens kundportfoelj."""),
            ("8.3 Exportformat", """Rapporter kan exporteras i foeljande format:

PDF: Formaterade rapporter med grafer och tabeller. Laemplig foer utskrift och arkivering.
Excel: Raadata med pivottabeller. Laemplig foer vidare analys.
CSV: Tidsseriedata foer import till tredjepartssystem.
JSON: Strukturerad data foer API-integration.

Automatisk distribution: Rapporter kan schemalaegas foer automatisk distribution via e-post till konfigurerade mottagare. Standard aer maanadsrapport den 1:a varje maaned."""),
        ]
    },
]


def generate_pdf():
    pdf = EMSDocPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.ln(60)
    pdf.cell(0, 15, "Solpulsen EMS", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 18)
    pdf.cell(0, 12, "Teknisk Dokumentation", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, "Version 2.1 - Februari 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Solpulsen Energy AB", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 8, "KONFIDENTIELLT - Endast foer intern anvaendning och godkaenda partners", align="C")

    # Table of contents
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Innehaallsfoerteckning", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    for ch in CHAPTERS:
        pdf.cell(0, 8, ch["title"], new_x="LMARGIN", new_y="NEXT")
        for sec_title, _ in ch["sections"]:
            pdf.cell(10)
            pdf.cell(0, 7, sec_title, new_x="LMARGIN", new_y="NEXT")

    # Content
    for ch in CHAPTERS:
        pdf.add_page()
        pdf.chapter_title(ch["title"])
        for sec_title, sec_text in ch["sections"]:
            pdf.section_title(sec_title)
            pdf.body_text(sec_text)

    pdf.output(OUTPUT_PATH)
    print(f"Generated PDF: {OUTPUT_PATH}")
    print(f"Pages: {pdf.page_no()}")
    return OUTPUT_PATH


if __name__ == "__main__":
    generate_pdf()
