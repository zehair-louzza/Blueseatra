# GPT-OSS pour le moteur texte

À la demande explicite de l'utilisateur du 5 octobre 2026, le modèle texte
principal devient `gpt-oss:20b` pour l'extraction et la structuration (il
remplace `qwen2.5:7b`). Le raisonnement de ces tâches est réglé sur `low`
(`HERMES_STRUCTURING_EFFORT`) ; le rôle `reason` garde son propre niveau
(`HERMES_REASONING_EFFORT`, `medium`). La configuration dédiée à la rédaction
reste inchangée ; les choix explicites d'entreprise continuent de primer selon
les règles de routage existantes.

## Routage

| Chemin | Modèle | Raisonnement | Repli |
|---|---|---|---|
| Texte collé (`role=extract`) | `HERMES_EXTRACT_MODEL` = `gpt-oss:20b` | `low` | `hermes3` (`HERMES_FALLBACK_MODELS`) |
| Fichier texte importé (cascade) | `HERMES_STRUCTURING_MODEL_1` = `gpt-oss:20b`, prompt complet puis compact | `low` | étage 3 `HERMES_STRUCTURING_MODEL_3` = `hermes3`, sans raisonnement |
| Vision générique (`role=file/vision`) | `HERMES_VISION_MODEL` = `qwen2.5vl:7b` | aucun | aucun (inchangé) |

La cascade OCR et le choix OCR propre à chaque entreprise restent distincts.
La préférence `paddleocr-vl` de l'entreprise configurée n'est pas remplacée
par ce changement du moteur texte.

- Le niveau `low` est transmis à Hermès dans `model_options.reasoning_effort`.
  Sur le chemin Ollama direct (retour arrière `BLUESEATRA_IA_VIA_HERMES=0`), il
  est envoyé comme `think: "low"`. La consigne de brièveté ne s'ajoute qu'aux
  modèles dont le raisonnement est un simple interrupteur, pas à gpt-oss.
- Les étiquettes de trace (`_structuring_engine`) suivent le modèle
  effectivement configuré (`GPT-OSS-20B`, `GPT-OSS-20B (compact)`,
  `Hermes-3`) et ne conservent jamais un nom Qwen après la bascule.
- Les timeouts de la cascade dépendent de la position de l'étage
  (`HERMES_STRUCTURATION_TIMEOUT_1/2/3`, 600/420/300 s), pas de l'étiquette :
  surcharger un modèle ne fait jamais perdre son timeout. Ces valeurs sont
  provisoires tant qu'aucune structuration complète par gpt-oss n'a été
  mesurée sur le VPS.
- Si une entreprise choisit explicitement GPT-OSS, ce modèle n'est jamais
  appelé avec une image : `role=file/vision` est redirigé vers
  `HERMES_VISION_MODEL`. Les autres choix explicites d'entreprise ne sont pas
  écrasés.
- `HERMES_VISION_MODEL` vide retombe désormais sur `qwen2.5vl:7b`. Il
  n'hérite plus de `HERMES_REASONING_MODEL`, qui est texte seul.

Les calculs commerciaux (prix, TVA, marges) et les garde-fous TCE ne sont pas
modifiés.

## Variables Render

`HERMES_EXTRACT_MODEL=gpt-oss:20b`, `HERMES_STRUCTURING_MODEL_1=gpt-oss:20b`,
`HERMES_STRUCTURING_EFFORT=low`, `HERMES_REASONING_MODEL=gpt-oss:20b`.
`HERMES_VISION_MODEL=qwen2.5vl:7b` reste explicite.

Décision de déploiement : le blueprint définissait jusqu'ici
`HERMES_REASONING_MODEL=qwen2.5vl:7b`. Passer à `gpt-oss:20b` aligne le rôle
`reason` (décomposition matériaux/lots) sur la valeur par défaut du code et
sur la demande de remplacer le moteur texte par GPT-OSS. Ce rôle produit des
propositions structurées, pas les calculs commerciaux : ceux-ci et les contrôles
FastAPI restent inchangés. Son effort dédié reste `medium`.

Les nouvelles valeurs s'ajoutent aux variables existantes ; les secrets ne
sont ni lus ni remplacés. `/api/health` expose `tce.text_model` et
`tce.structuring_model`, qui indiquent la configuration et non le modèle qui a
réellement répondu.
