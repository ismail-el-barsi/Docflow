C’est une façon d’organiser les données par niveau de transformation. On appelle ça une architecture `Medallion`.

Dans ce projet :

- `Bronze`
  - sert à garder la donnée brute
  - dans ce projet : le PDF uploadé + les métadonnées minimales
  - objectif : conserver la source d’origine sans modification

- `Silver`
  - sert à stocker la donnée nettoyée / structurée
  - dans ce projet : OCR + classification + extraction des champs utiles
  - objectif : avoir une version exploitable techniquement

- `Gold`
  - sert à stocker la donnée enrichie pour le métier
  - dans ce projet : extraction + alertes de fraude + statut de conformité
  - objectif : alimenter directement le dashboard, le CRM, les vues métier

Pourquoi c’est utile :
- on sépare le brut du transformé
- on peut rejouer un traitement sans perdre la source
- on peut débugger plus facilement
- on évite de mélanger données techniques et données métier
- c’est plus propre pour expliquer le pipeline

Dans ce flow :
1. utilisateur upload un PDF
2. il va en `bronze`
3. le pipeline fait OCR/classification/extraction
4. le résultat va en `silver`
5. les règles de cohérence/fraude s’appliquent
6. le résultat final va en `gold`

Exemple simple :
- `bronze` : `facture_acme.pdf`
- `silver` : `siren=123456789`, `ttc=1200`, `date=2026-03-17`
- `gold` : mêmes données + `alerte: montant incohérent`, `is_compliant=false`

Donc :
- `bronze` = archive brute
- `silver` = donnée traitée
- `gold` = donnée métier finale
