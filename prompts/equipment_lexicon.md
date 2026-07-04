# Equipment Vocabulary Lexicon — v0.1

*The base vocabulary layer for the general agent. Feeds the HyDE question-generation prompt so synthetic questions are generated in the words crew actually use — across regions and languages — not just the formal terms a manual prints. Per-vessel vocabulary (sensor channel names, vessel-specific acronyms harvested from the folder tree) is layered on top of this base during onboarding.*

**Status: living document.** v0.1 seeds the engineering-critical categories from established marine terminology. The deep-research expansion (flagged sections below) verifies and extends the regional and slang coverage.

---

## How this is used

During HyDE generation, the agent looks up the equipment category of a chunk and injects the matching vocabulary row into the generation prompt. The model then produces synthetic questions using *all* the listed terms — so a chunk from a "main engine" manual becomes retrievable whether the engineer types "main engine," "the donk," "motore principale," or "Hauptmotor."

**Sourcing rules (for the expansion pass):**
- Include the **most common, mutually-understood** terms and the words **crew actually use** — sourced from manuals, supplier sites, and crew forums.
- Include slang only where it is genuinely in use and unambiguous.
- **Exclude** class-society and flag-state terminology — too formal, not how crew talk.
- When uncertain about a regional term or a piece of slang, flag it for verification rather than assert it.

**Languages targeted (full matrix, expansion pass):** English (US · UK · South Africa · Australia · New Zealand · Canada), Spanish (Spain · Latin America), Italian, French (north · south), Dutch, German — plus others as crewing demographics demand (Greek, Croatian, Portuguese, Tagalog flagged for later).

**v0.1 coverage:** English (general + confident slang), Spanish, Italian, French, Dutch, German for the core engineering categories. Regional English sub-variants and forum-sourced slang marked **[RESEARCH]** where not yet verified.

---

## 400 — Propulsion & Machinery

### Propulsion motor / main engine
- **English:** main engine, the main, the mains, engine, motor, prop motor, drive motor; (electric/hybrid) traction motor, e-motor; *slang:* the donk / donkey (UK, AU, NZ), the donk [RESEARCH: SA usage]
- **Spanish:** motor principal, motor de propulsión; (LatAm) motor principal
- **Italian:** motore principale, motore di propulsione
- **French:** moteur principal, moteur de propulsion
- **Dutch:** hoofdmotor, voortstuwingsmotor
- **German:** Hauptmotor, Antriebsmotor

### Gearbox / transmission
- **English:** gearbox, gear, the box, transmission, GB, reduction gear, reverse gear
- **Spanish:** caja reductora, inversor reductor, reductora
- **Italian:** invertitore, riduttore, invertitore-riduttore
- **French:** inverseur, réducteur, inverseur-réducteur
- **Dutch:** keerkoppeling, tandwielkast
- **German:** Wendegetriebe, Getriebe, Untersetzungsgetriebe

### Propeller / controllable-pitch propeller (CPP)
- **English:** prop, propeller, screw, wheel (US), CPP, controllable-pitch propeller, variable pitch, the pitch, VP box; (maker used generically) "Hundested"
- **Spanish:** hélice, hélice de paso variable
- **Italian:** elica, elica a passo variabile
- **French:** hélice, hélice à pas variable
- **Dutch:** schroef, verstelbare schroef
- **German:** Propeller, Verstellpropeller

### Shaft & shaft seal
- **English:** shaft, propshaft, prop shaft, shaft line, tail shaft; shaft seal, stern gland, stuffing box
- **Spanish:** eje, línea de ejes; bocina, sello de eje, prensaestopas
- **Italian:** asse, linea d'assi; tenuta dell'asse, premistoppa
- **French:** ligne d'arbre, arbre d'hélice; presse-étoupe, joint d'arbre
- **Dutch:** schroefas; schroefasafdichting, pakkingbus
- **German:** Welle, Propellerwelle; Wellendichtung, Stopfbuchse

### Thrusters (bow / stern)
- **English:** bow thruster, stern thruster, thruster, the thrusters
- **Spanish:** hélice de proa, hélice de popa, propulsor de proa/popa
- **Italian:** elica di prua, elica di poppa
- **French:** propulseur d'étrave, propulseur de poupe
- **Dutch:** boegschroef, hekschroef
- **German:** Bugstrahlruder, Heckstrahlruder

### Exhaust
- **English:** exhaust, wet exhaust, exhaust system
- **Spanish:** escape, sistema de escape
- **Italian:** scarico, impianto di scarico
- **French:** échappement, ligne d'échappement
- **Dutch:** uitlaat, uitlaatsysteem
- **German:** Abgasanlage, Auspuff

---

## 100 — Structure, Rudder & Keel

### Steering system
- **English:** steering, steering gear, the helm, the quadrant, steering system
- **Spanish:** sistema de gobierno, aparato de gobierno, timonería
- **Italian:** timoneria, apparato di governo
- **French:** appareil à gouverner, barre, système de direction
- **Dutch:** stuurinrichting, stuurmachine
- **German:** Ruderanlage, Steuerung

### Rudder
- **English:** rudder, the blade, rudder stock
- **Spanish:** timón, mecha del timón
- **Italian:** timone, asse del timone
- **French:** safran, mèche de safran
- **Dutch:** roer, roerkoning
- **German:** Ruder, Ruderschaft

### Keel
- **English:** keel, the keel, lifting keel, canting keel, the bulb, ballast
- **Spanish:** quilla, quilla abatible, bulbo, lastre
- **Italian:** chiglia, chiglia mobile, bulbo, zavorra
- **French:** quille, quille relevable, quille pendulaire, bulbe, lest
- **Dutch:** kiel, hefkiel, kantelkiel, ballast
- **German:** Kiel, Hubkiel, Schwenkkiel, Ballast

---

## 600 — Electric Systems

### Generator
- **English:** generator, gen, genny, genset, the gennies, diesel genset
- **Spanish:** generador, grupo electrógeno, el grupo
- **Italian:** generatore, gruppo elettrogeno
- **French:** groupe électrogène, le groupe, générateur
- **Dutch:** generator, aggregaat, generatorset
- **German:** Generator, Aggregat, Stromaggregat

### Battery / energy storage
- **English:** battery, batteries, the bank, the banks, the pack, house bank, start bank, ESS, traction battery, lithium bank
- **Spanish:** batería, baterías, banco de baterías, parque de baterías
- **Italian:** batteria, batterie, banco batterie, parco batterie
- **French:** batterie, batteries, parc de batteries, parc batterie
- **Dutch:** accu, accu's, accubank, batterijbank
- **German:** Batterie, Batterien, Batteriebank, Akku

### Inverter / charger
- **English:** inverter, charger, inverter-charger, the inverters
- **Spanish:** inversor, cargador, inversor-cargador
- **Italian:** inverter, caricabatterie
- **French:** convertisseur, chargeur, onduleur
- **Dutch:** omvormer, lader, omvormer-lader
- **German:** Wechselrichter, Ladegerät, Laderegler

### Switchboard / distribution
- **English:** switchboard, the board, the boards, distribution board, panel, AC board, DC board, main board, MSB
- **Spanish:** cuadro eléctrico, cuadro de distribución, panel
- **Italian:** quadro elettrico, quadro di distribuzione
- **French:** tableau électrique, tableau de distribution, TGBT
- **Dutch:** schakelbord, verdeelkast, paneel
- **German:** Schalttafel, Verteilung, Verteilerkasten

### Shore power
- **English:** shore power, the shore lead, shore connection, dockside power
- **Spanish:** toma de tierra, conexión de puerto, alimentación de puerto
- **Italian:** presa di banchina, alimentazione da terra
- **French:** prise de quai, alimentation à quai
- **Dutch:** walstroom, walaansluiting
- **German:** Landstrom, Landanschluss

### Cathodic protection / anodes
- **English:** anodes, sacrificial anodes, CP, cathodic protection, zincs (US), the zincs
- **Spanish:** ánodos, ánodos de sacrificio, protección catódica
- **Italian:** anodi, anodi sacrificali, protezione catodica
- **French:** anodes, anodes sacrificielles, protection cathodique
- **Dutch:** anodes, opofferingsanodes, kathodische bescherming
- **German:** Anoden, Opferanoden, kathodischer Schutz

---

## 500 — Systems (fluid, climate, services)

### Pumps (general + by duty)
- **English:** pump; bilge pump, fire pump, fresh-water pump, sea-water / raw-water pump, fuel pump, transfer pump, circulation pump
- **Spanish:** bomba; bomba de achique (bilge), bomba contraincendios (fire), bomba de agua dulce, bomba de agua de mar, bomba de combustible, bomba de trasiego
- **Italian:** pompa; pompa di sentina (bilge), pompa antincendio (fire), pompa acqua dolce, pompa acqua mare, pompa carburante, pompa di travaso
- **French:** pompe; pompe de cale (bilge), pompe incendie (fire), pompe eau douce, pompe eau de mer, pompe à carburant, pompe de transfert
- **Dutch:** pomp; lenspomp (bilge), brandbluspomp (fire), drinkwaterpomp, zeewaterpomp, brandstofpomp, overpomp
- **German:** Pumpe; Lenzpumpe (bilge), Feuerlöschpumpe (fire), Frischwasserpumpe, Seewasserpumpe, Kraftstoffpumpe, Transferpumpe

### Heat exchanger / cooler
- **English:** heat exchanger, cooler, HEX, intercooler, charge-air cooler, keel cooler
- **Spanish:** intercambiador de calor, enfriador, refrigerador
- **Italian:** scambiatore di calore, refrigeratore
- **French:** échangeur de chaleur, refroidisseur
- **Dutch:** warmtewisselaar, koeler
- **German:** Wärmetauscher, Kühler

### Watermaker
- **English:** watermaker, the maker, RO, reverse osmosis, desal, desalinator
- **Spanish:** potabilizadora, desalinizadora, ósmosis
- **Italian:** dissalatore, osmosi
- **French:** dessalinisateur, osmoseur
- **Dutch:** watermaker, ontziltingsinstallatie
- **German:** Wassermacher, Entsalzungsanlage, Umkehrosmose

### Air conditioning
- **English:** air con, AC, HVAC, chilled water, the chiller
- **Spanish:** aire acondicionado, climatización, enfriadora
- **Italian:** aria condizionata, climatizzazione, refrigeratore
- **French:** climatisation, clim, groupe froid
- **Dutch:** airconditioning, koeling
- **German:** Klimaanlage, Klimatisierung

### Refrigeration
- **English:** fridge, reefer, refrigeration, freezer
- **Spanish:** refrigeración, nevera, congelador
- **Italian:** refrigerazione, frigo, congelatore
- **French:** réfrigération, frigo, congélateur
- **Dutch:** koeling, koelkast, vriezer
- **German:** Kälteanlage, Kühlung, Gefrierschrank

### Power hydraulic system
- **English:** hydraulics, the power pack, PTO, power take-off, hydraulic pump, the rams
- **Spanish:** sistema hidráulico, central hidráulica, grupo hidráulico, toma de fuerza
- **Italian:** impianto idraulico, centralina idraulica, presa di forza
- **French:** circuit hydraulique, centrale hydraulique, prise de force
- **Dutch:** hydrauliek, hydraulisch aggregaat, aftakas
- **German:** Hydraulik, Hydraulikaggregat, Nebenabtrieb

### Fire suppression *(critical — engine-room flooding)*
- **English:** fire suppression, the suppression system, FM200, gas system, vent shutters, fire dampers
- **Spanish:** sistema de extinción, extinción por gas, compuertas de ventilación
- **Italian:** impianto di estinzione, estinzione a gas, serrande di ventilazione
- **French:** système d'extinction, extinction par gaz, volets de ventilation
- **Dutch:** blussysteem, gasblussing, ventilatiekleppen
- **German:** Löschanlage, Gaslöschanlage, Lüftungsklappen

### Bilge & fire (firefighting pump system) *(critical)*
- **English:** bilge system, fire pump, fire main, hydrants, the bilge
- **Spanish:** sistema de achique, colector contraincendios, bocas/hidrantes
- **Italian:** impianto di sentina, collettore antincendio, idranti
- **French:** circuit de cale, collecteur incendie, bouches/hydrants
- **Dutch:** lenssysteem, brandblusleiding, brandkranen
- **German:** Lenzsystem, Feuerlöschleitung, Hydranten

---

## 200 / 800 — Deck & Rigging

### Winches
- **English:** winch, winches, primary, primaries, grinder, grinders, the pedestals
- **Spanish:** winche, winches, cabrestante
- **Italian:** verricello, winch, verricelli
- **French:** winch, treuil, winchs
- **Dutch:** lier, lieren
- **German:** Winsch, Winschen

### Anchor windlass / ground tackle
- **English:** windlass, the hook, anchor, ground tackle, capstan, chain
- **Spanish:** molinete, ancla, cabrestante, cadena
- **Italian:** salpancore, verricello salpancore, ancora, catena
- **French:** guindeau, ancre, cabestan, chaîne
- **Dutch:** ankerlier, anker, kaapstander, ketting
- **German:** Ankerwinde, Anker, Spill, Kette

### Mast / rig
- **English:** mast, the rig, the stick, spar
- **Spanish:** palo, mástil, arboladura
- **Italian:** albero, alberatura
- **French:** mât, gréement
- **Dutch:** mast, tuigage
- **German:** Mast, Rigg

### Boom
- **English:** boom, main boom
- **Spanish:** botavara
- **Italian:** boma
- **French:** bôme
- **Dutch:** giek
- **German:** Baum, Großbaum

### Sails
- **English:** sails, main, mainsail, jib, genoa, staysail, code zero, spinnaker, kite
- **Spanish:** velas, mayor, foque, génova, trinquetilla
- **Italian:** vele, randa, fiocco, genoa
- **French:** voiles, grand-voile, foc, génois
- **Dutch:** zeilen, grootzeil, fok, genua
- **German:** Segel, Großsegel, Fock, Genua

### Furlers
- **English:** furler, the furlers, furling system, in-mast / in-boom furling
- **Spanish:** enrollador, sistema de enrollado
- **Italian:** avvolgitore, sistema di avvolgimento
- **French:** enrouleur, système d'enroulement
- **Dutch:** rolsysteem, oproller
- **German:** Furler, Rollanlage

### Sailing hydraulics
- **English:** sailing hydraulics, the rams, cylinders, cunningham, vang, outhaul (hydraulic functions)
- **Spanish:** hidráulica de jarcia, cilindros
- **Italian:** idraulica di coperta, cilindri
- **French:** hydraulique de pont, vérins
- **Dutch:** zeilhydrauliek, cilinders
- **German:** Segelhydraulik, Zylinder

---

## 900 — Miscellaneous

### Dive compressor
- **English:** dive compressor, the compressor, breathing-air compressor
- **Spanish:** compresor de buceo, compresor de aire respirable
- **Italian:** compressore subacqueo, compressore aria respirabile
- **French:** compresseur de plongée, compresseur d'air respirable
- **Dutch:** duikcompressor, ademluchtcompressor
- **German:** Tauchkompressor, Atemluftkompressor

### Tender & handling
- **English:** tender, the toy, RIB, davit, passerelle, gangway, haul winch
- **Spanish:** auxiliar, neumática, pescante, pasarela
- **Italian:** tender, gommone, gru, passerella
- **French:** annexe, semi-rigide, bossoir, passerelle
- **Dutch:** bijboot, davit, loopplank
- **German:** Beiboot, Davit, Gangway

---

## Expansion plan (deep-research pass)

1. **Regional English sub-variants** — verify and add US / UK / SA / AU / NZ / CA divergences (e.g. "zincs" vs "anodes," "wheel" vs "prop," regional slang) from crew forums and regional supplier sites. Currently marked **[RESEARCH]** or folded into general English.
2. **Crew slang verification** — confirm every slang term is genuinely in use and unambiguous before it ships; cut anything speculative.
3. **Additional languages** — Greek, Croatian, Portuguese, Tagalog as crewing demographics warrant.
4. **Remaining equipment categories** — extend to the lighter Ontology categories (interiors appliances, nav/comms, entertainment, safety gear, sensors/PLCs) once the engineering-critical core above is verified.
5. **Per-source citation** — note where each non-obvious term was sourced (manual / supplier / forum) so the table is auditable.

## Changelog

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-05-23 | Seed — engineering-critical categories across EN/ES/IT/FR/NL/DE from established marine terminology. Regional sub-variants and forum slang flagged for the research pass. |
