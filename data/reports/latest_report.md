# Rapport d'Analyse Logistique — Pipeline UNIX & Gouvernance Iragi

**Horodatage de generation** : 2026-11-26 18:14:23 UTC  
**Statut d'orchestration** : `SUCCESS`  
**Version d'audit `iragi`** : `0.6.4`

---

## 1. Comparaison : Brut vs Approche Classique vs Pipeline UNIX + Iragi

| Indicateur d'Audit | 1. Brut (`data/raw`) | 2. Approche Classique Naive | 3. Pipeline UNIX + `iragi` |
| :--- | :---: | :---: | :---: |
| Enregistrements retenus | 2555 | 2520 | **2510** |
| Score de qualite `iragi.scan` (/100) | 99.29 | Non certifie | **99.75** (+0.46 pts) |
| Doublons actifs | 35 | 0 | **0** |
| Violations du `DataContract` | 12 | **10** (non filtrees) | **0** |
| Tracabilite Quarantaine DLQ | Aucune | Aucune (imputation aveugle) | **10 lignes isolees** |
| Orphelins HTTP `404` non reconcilies | 139 | 139 | **0 ignore (139 identifies)** |

### Detail des violations detectees AVANT nettoyage (`iragi.DataContract`)
- Colonne `id` (regle `not_null`) : **1** violation(s) detectee(s)
- Colonne `ville` (regle `not_null`) : **1** violation(s) detectee(s)
- Colonne `date` (regle `regex`) : **1** violation(s) detectee(s)
- Colonne `poids` (regle `range`) : **3** violation(s) detectee(s)
- Colonne `distance` (regle `range`) : **2** violation(s) detectee(s)
- Colonne `temps` (regle `range`) : **2** violation(s) detectee(s)
- Colonne `temps_prevu` (regle `range`) : **1** violation(s) detectee(s)
- Colonne `statut` (regle `regex`) : **1** violation(s) detectee(s)

### Reconciliation Inter-Sources (`iragi.reconcile` : CSV vs Logs Apache)
- Livraisons rapprochees avec les appels `/api/livraisons/LIV-<id>` de `access.log` : **751** (couverture : **28.35 %**).
- Requetes HTTP `404` orphelines pointant vers des identifiants inexistants : **139**.

---

## 2. Statistiques Descriptives, Quartiles et Correlations (2510 Livraisons)

| Variable | Effectif | Moyenne | Mediane | Q1 | Q3 | IQR | Min | Max | Ecart-type |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| poids | 2510 | 27.17 | 26.97 | 15.44 | 38.75 | 23.31 | 5.01 | 49.99 | 13.20 |
| distance | 2510 | 136.00 | 53.00 | 31.00 | 233.00 | 202.00 | 10.00 | 500.00 | 141.71 |
| temps | 2510 | 128.55 | 88.00 | 53.00 | 213.00 | 160.00 | 30.00 | 300.00 | 89.14 |
| temps_prevu | 2510 | 131.96 | 89.00 | 55.00 | 216.00 | 161.00 | 30.00 | 285.00 | 91.48 |
| cout_livraison | 2510 | 45.58 | 40.41 | 27.74 | 60.79 | 33.05 | 8.25 | 128.95 | 24.03 |
| speed_kmh | 2510 | 51.08 | 47.20 | 31.30 | 69.51 | 38.21 | 8.57 | 124.52 | 24.40 |

- **Correlation Distance vs Temps** : `r = 0.9296` (association lineaire forte ; une correlation n'implique pas a elle seule une causalite unique sans controle des facteurs trafic/vehicule).
- **Correlation Poids vs Temps** : `r = -0.1073`.
- **Correlation Distance vs Cout** : `r = 0.8647`.

---

## 3. Performances par Ville de Destination (9 Villes)

| Ville | Livraisons | Poids moy. (kg) | Distance moy. (km) | Duree moy. (min) | Vitesse moy. (km/h) | Cout moy. | Taux de retard |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Paris | 377 | 27.15 | 75.59 | 90.96 | 40.24 | 36.67 EUR | 14.59 % |
| Lyon | 320 | 26.98 | 136.42 | 131.01 | 50.86 | 45.67 EUR | 11.88 % |
| Marseille | 307 | 27.91 | 157.63 | 139.18 | 54.55 | 48.80 EUR | 11.40 % |
| Toulouse | 268 | 27.99 | 142.35 | 131.46 | 53.28 | 46.76 EUR | 7.46 % |
| Lille | 265 | 27.13 | 138.65 | 130.29 | 51.56 | 46.14 EUR | 10.57 % |
| Bordeaux | 257 | 27.18 | 161.35 | 144.07 | 55.13 | 48.89 EUR | 14.40 % |
| Nantes | 245 | 26.29 | 152.21 | 142.16 | 54.11 | 47.98 EUR | 8.57 % |
| Strasbourg | 237 | 25.90 | 152.47 | 137.09 | 54.17 | 47.15 EUR | 6.75 % |
| Nice | 234 | 27.79 | 132.57 | 126.53 | 50.53 | 45.91 EUR | 11.97 % |

---

## 4. Comparaison par Type de Vehicule

| Vehicule | Livraisons | Distance moy. | Duree moy. | Vitesse moy. | Cout moy. | Taux de retard |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Camionnette | 1027 | 124.02 km | 117.15 min | 50.49 km/h | 42.11 EUR | 12.46 % |
| Fourgon | 998 | 197.57 km | 157.45 min | 64.97 km/h | 62.33 EUR | 10.02 % |
| Moto | 322 | 34.84 km | 72.11 min | 28.14 km/h | 20.56 EUR | 10.25 % |
| Velo | 163 | 34.29 km | 134.90 min | 15.09 km/h | 14.36 EUR | 10.43 % |

---

## 5. Visualisations Generees (`gnuplot`)

1. `../visualizations/01_livraisons_par_ville.png` — Volume de livraisons par ville
2. `../visualizations/02_evolution_mensuelle.png` — Evolution mensuelle des livraisons
3. `../visualizations/03_taux_retard_par_ville.png` — Taux de retard par ville
4. `../visualizations/04_distribution_temps.png` — Distribution des temps de livraison
5. `../visualizations/05_distance_vs_temps.png` — Distance versus temps
6. `../visualizations/06_repartition_statuts.png` — Repartition des statuts
7. `../visualizations/07_performance_livreurs.png` — Performance des livreurs
8. `../visualizations/08_anomalies_avant_apres.png` — Comparaison des anomalies avant et apres traitement

---

## 6. Recommandations Operationnelles

1. **Renforcer le suivi des corridors vers Paris (14.59 % de retard)** en comparant l'allocation flotte avec **Strasbourg** (**6.75 %**).
2. **Appliquer `iragi.DataContract` en entree API** pour rejeter avant ingestion les dates invalides, poids negatifs et distances hors-contrat.
3. **Auditer le service API emettant les 139 appels HTTP `404` orphelins** sur `/api/livraisons/LIV-*`.
