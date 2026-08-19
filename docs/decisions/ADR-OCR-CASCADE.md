# ADR : cascade OCR multi-modèles pour l'extraction de fichiers importés

## Statut
Accepté — 2026-08-18/19

## Contexte

L'extraction de fichiers importés (PDF illisible, image/photo) reposait
uniquement sur `gemma4:26b` en vision directe : fiable mais lent
(~600-750s/page mesuré sur le VPS CPU-only, 8 vCPU sans GPU) car le
raisonnement de Gemma doit à la fois lire l'image ET structurer le
résultat en JSON.

Demande initiale : installer **PaddleOCR-VL-1.6**, **DeepSeek-OCR-2** et
**Phi-4-reasoning-vision-15B**, avec Gemma comme orchestrateur/juge
déterminant si le rendu d'un modèle est acceptable ou s'il faut escalader
vers le modèle suivant, du moins performant au plus performant.

## Modèles évalués (8 au total)

Chaque modèle a été testé en conditions réelles sur le VPS
(`162.19.44.2`) avec le même document réel (PDF `LOT_20_LA_SABLIERE`,
rendu en image composite), via l'API Ollama derrière Hermes
(`https://ia.blueseatra.com/api/chat`).

| Modèle | Taille | Durée mesurée | Résultat | Décision |
|---|---|---|---|---|
| **PaddleOCR-VL-1.6** | 0.9B | ~110s | Transcription littérale fidèle ; a échoué une fois sur une image composite à 3 pages (erreur serveur `peg-native format`) | ✅ Étape 1 (le plus rapide) |
| **LightOnOCR-2-1B** | 596M | ~200s | SOTA OlmOCR-Bench (83.2), sortie Markdown/HTML bien structurée (tableaux avec rowspan/colspan corrects), entraîné avec forte couverture de documents **français** — aucun échec observé | ✅ Étape 2 (le plus fiable) |
| **Qwen2.5-VL-7B** | 8.3B | ~246s | Officiel bibliothèque Ollama (pas de GGUF communautaire à risque), excellente fidélité, structure bien les tableaux | ✅ Étape 3 (avant le recours à Gemma) |
| **olmOCR-2-7B** (Q8) | 7.6B | ~587s | Qualité de structuration exceptionnelle (tableau HTML avec rowspan/colspan), mais lent (quant 8-bit lourd) | ⚠️ Disponible mais non câblé par défaut (redondant avec Qwen2.5-VL, plus lent) |
| **gemma4:26b** (vision directe) | 26B | ~600-750s | Fiable, déjà en production, sert aussi de structuration finale de tout texte OCR | ✅ Étape 4 — secours final |
| **Phi-4-reasoning-vision-15B** | 15B | ~751s (12,5 min) | Fonctionne (vision confirmée via `ollama show`) mais **paraphrase au lieu de transcrire littéralement** et fait des erreurs d'entités (ex. « SAIN-S0263 » au lieu de « SAYN-S0263 ») | ⚠️ Escalade **manuelle uniquement** (bouton, jamais automatique) |
| **DeepSeek-OCR-2** (GGUF communautaire) | 3B (pas 7B) | — | Commence correctement puis **invente du texte juridique inexistant**, dégénère en caractères chinois répétés en boucle | ❌ Rejeté |
| **GLM-4.1V-9B-Thinking** | 9.4B | — | Toutes les conversions GGUF disponibles (unsloth, mradermacher, Mungert) sont **texte seul** — aucun fichier `mmproj`, capacité vision absente (confirmé via `ollama show`) | ❌ Rejeté — pas de vision fonctionnelle |
| **Granite Vision 3.2-2B** | 2.5B | ~263s | Texte décousu, invente des mots (« INTELLIGENCE » apparu de nulle part), inverse des chiffres, **dégénère en répétant le même paragraphe en boucle** | ❌ Rejeté |

Deux corrections factuelles importantes par rapport à la demande initiale :
- **DeepSeek-OCR-2 est un modèle 3B**, pas 7B (décodeur MoE ~500M actifs par token).
- **Phi-4-reasoning-vision-15B existe réellement** (sorti mars 2026, MIT, 16K contexte) mais son écosystème GGUF communautaire est immature : plusieurs conversions largement diffusées sont en réalité *texte seul* malgré leur nom.

## Décision

### Architecture retenue : cascade séquentielle, pas de juge LLM dédié

Plutôt qu'un appel Gemma dédié à juger chaque tentative (coût : un swap
mémoire + un appel de raisonnement supplémentaire par étape, sur un VPS
limité à 18 Go pour Ollama avec `OLLAMA_MAX_LOADED_MODELS=1`), le rôle de
juge est assuré par **deux filtres déterministes bon marché** :

1. `_ocr_result_acceptable(text)` — rejette un texte OCR trop court ou
   charabia (même logique que `_looks_garbled`, appliquée à la sortie de
   l'OCR plutôt qu'au calque texte PDF d'origine).
2. `_extraction_seems_incomplete(extracted, source_text)` — après que
   Gemma a structuré le texte OCR en JSON, rejette un résultat avec une
   erreur, une confiance très basse, ou aucune ligne/description malgré
   un texte source substantiel.

Si une étape échoue ces filtres, la cascade passe à l'étape suivante.
Gemma reste l'unique moteur de **structuration** (JSON), jamais remplacé
par les modèles OCR — ceux-ci ne font QUE de la transcription littérale.

```
Image/PDF illisible
  │
  ├─ 1. PaddleOCR-VL-1.6 (transcription, ~110s)
  │     └─ filtre + Gemma structure (texte) → si insuffisant, étape 2
  ├─ 2. LightOnOCR-2-1B (transcription, ~200s)
  │     └─ filtre + Gemma structure (texte) → si insuffisant, étape 3
  ├─ 3. Qwen2.5-VL-7B (transcription, ~246s)
  │     └─ filtre + Gemma structure (texte) → si insuffisant, étape 4
  └─ 4. Gemma vision directe (secours final, ~600-750s)

  [Bouton manuel séparé, jamais automatique]
  → Phi-4-reasoning-vision-15B (~10-15 min, à comparer, pas à substituer)
```

### Traitement page par page (pas d'image composite empilée)

Une image composite multi-pages (plusieurs pages de PDF empilées
verticalement en une seule image) peut dépasser les limites de
résolution/aspect-ratio de certains modèles OCR spécialisés : observé en
conditions réelles, PaddleOCR-VL-1.6 a échoué avec une erreur HTTP 500
sur une image à 3 pages empilées, alors qu'il réussit systématiquement
sur les mêmes pages traitées individuellement. Chaque page d'un PDF est
donc rendue et traitée séparément par la cascade OCR ; le texte de toutes
les pages est concaténé puis structuré en UNE SEULE fois par Gemma
(évite de payer N fois le coût de structuration). Si une page échoue
toutes les étapes OCR, le secours vision directe de Gemma ne s'applique
qu'à CETTE page, pas au document entier.

### Règle de timeout par étage (1,2x la durée de l'étape suivante)

Plutôt qu'un timeout fixe arbitraire par modèle, chaque étape de la
cascade a un timeout calculé dynamiquement : **1,2 x la durée réelle
mesurée de l'étape SUIVANTE** (plus lente mais plus fiable/puissante).
Objectif : ne jamais attendre sur un modèle bloqué ou dégradé plus
longtemps que ce qu'il faudrait de toute façon pour que l'étape suivante
fasse le travail, avec une marge réduite à 20 %. Valeurs calculées
(mesures 2026-08-18/19) :

| Étape | Durée mesurée | Timeout appliqué (1,2x l'étape suivante) |
|---|---:|---:|
| PaddleOCR-VL-1.6 | ~110s | 240s (1,2 x 200, LightOnOCR) |
| LightOnOCR-2-1B | ~200s | 295s (1,2 x 246, Qwen2.5-VL) |
| Qwen2.5-VL-7B | ~246s | 704s (1,2 x 587, olmOCR-2) |
| olmOCR-2-7B | ~587s | 780s (1,2 x 650, Gemma-vision) |
| Gemma vision directe (dernier étage) | ~600-750s | plafond fixe existant (900s raisonnement) |

Ce multiplicateur était initialement fixé à 1,5x puis réduit à 1,2x le
même jour pour limiter davantage la latence pire cas. Constante
`_OCR_STAGE_TIMEOUT_MULTIPLIER` dans `ai_service.py`, ajustable sans
toucher au reste de la logique.

### olmOCR-2-7B ajouté comme 4e étage automatique

Après les trois premiers modèles, **olmOCR-2-7B** (fine-tune de
Qwen2.5-VL-7B par renforcement, spécifiquement pour l'OCR) est ajouté
comme 4e étage : fiabilité confirmée (aucune hallucination observée),
meilleure fidélité de structure de tableau (HTML avec rowspan/colspan
corrects) parmi tous les modèles testés, mais le plus lent des quatre
(~587s, quantification Q8_0 lourde) — dernier recours OCR avant la
vision directe de Gemma.

### Pourquoi pas de véritable "juge IA" par étape

- Chaque swap de modèle sur ce VPS coûte du temps de chargement (17 Go
  pour Gemma) en plus du temps de génération — un juge dédié aurait
  ajouté un aller-retour supplémentaire par étape.
- Les signaux déterministes (JSON valide, champs critiques présents,
  cohérence longueur texte/résultat) couvrent la plupart des échecs
  réels observés (réponse vide, erreur serveur, structuration ratée) sans
  coût de raisonnement supplémentaire.
- Gemma reste "juge" dans un sens plus large : c'est lui qui décide, en
  structurant le texte OCR, si le contenu produit une extraction valide —
  son échec (`_error`, confiance basse) déclenche directement l'étape
  suivante.

### Contrainte respectée : jamais de repli heuristique sur fichier

Conformément à la règle déjà en vigueur (voir `ADR` extraction et skill
`intake-demande-devis` §0ter) : si toutes les étapes échouent, la demande
passe en statut `failed` explicite — jamais un résultat vide présenté
comme valide.

### Remplacement de la case "Contenu source"

L'ancienne case affichait le texte brut du fichier (calque PDF, texte
collé, ou rien pour une image). Elle est remplacée par **"Extraction
IA"** qui affiche :
- Le texte produit par le modèle OCR qui a réussi (`_ocr_text`), avec un
  badge indiquant lequel (`_ocr_engine`).
- Si aucun texte OCR n'a été capturé (cas du secours vision directe de
  Gemma sans étape OCR intermédiaire) : une note explicite plutôt qu'un
  champ vide trompeur.
- Pour les fichiers texte natifs (DOCX/XLSX/CSV/TXT/texte collé) : le
  texte lu reste éditable (flux existant), relabellisé honnêtement comme
  "texte transmis à l'IA" plutôt que "contenu source".
- Un bouton d'escalade manuelle vers Phi-4-reasoning-vision-15B,
  disponible uniquement pour les photos (seul type de fichier dont
  l'octet original reste en base — les PDF ne sont jamais stockés).

## Conséquences

- Nouvelles variables d'environnement (toutes surchargeables, valeurs
  par défaut = modèles retenus) : `HERMES_OCR_MODEL`,
  `HERMES_OCR_SECONDARY_MODEL`, `HERMES_OCR_ESCALATION_MODEL`,
  `HERMES_ESCALATION_VISION_MODEL`.
- Nouveaux modèles à installer sur le VPS (`ovh-ai-stack`, Ollama) :
  `AuditAid/PaddleOCR-VL-1.6-0.9B` (1.8 Go), `maternion/LightOnOCR-2:1b`
  (1.7 Go), `qwen2.5vl:7b` (6.0 Go), et en option manuelle
  `hf.co/DevQuasar/microsoft.Phi-4-reasoning-vision-15B-GGUF:Q4_K_M`
  (9.9 Go). Total ~19 Go supplémentaires, largement dans le budget
  disque (127 Go libres au moment de la décision).
- `OLLAMA_MAX_LOADED_MODELS=1` / `OLLAMA_NUM_PARALLEL=1` restent
  nécessaires : aucune coexistence possible en mémoire (18 Go de limite
  Ollama) entre ces modèles et Gemma (17 Go seul).
- Nouvel endpoint `POST /requests/{id}/deep-vision` (traitement en
  arrière-plan, jamais synchrone — le proxy HTTP de Render tuerait une
  requête de 10-15 min) pour l'escalade manuelle Phi-4.
- Le pire cas de latence (toutes les étapes échouent avant le secours
  Gemma) devient : ~110 + 200 + 246 + 650 ≈ 1200s (~20 min). Cas rare en
  pratique — Paddle ou LightOnOCR réussissent la grande majorité du
  temps d'après les tests.
</content>
