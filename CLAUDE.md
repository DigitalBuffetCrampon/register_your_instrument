# CLAUDE.md — Formulaire d'enregistrement instrument · Buffet Crampon

## Contexte
Formulaire web permettant aux musiciens d'enregistrer leur instrument Buffet Crampon (toutes marques actives).

**Remplace le projet NFT** — décommissionné en avril 2026 (ROI insuffisant).
Le flux technique est identique au projet NFT (même stack n8n → PostgreSQL CDP → BigQuery) mais étendu à toutes les marques et familles d'instruments, et sans la couche Arianee.

> Statut : en développement — architecture définie, formulaire et workflow n8n à construire (bloqué sur catalogue AX)

---

## Décisions d'architecture

| Décision | Choix | Raison |
|---|---|---|
| Hébergement formulaire | Landing page HTML autonome | Indépendant de Magento / agence Modulo |
| Périmètre marques | Toutes les marques actives BC | Source : catalogue AX (ERP Microsoft Dynamics) |
| Catalogue instruments | Récupéré depuis AX | Source de vérité instruments |
| Base opérationnelle | PostgreSQL CDP (OVH VPS) | Cohérence avec stack CDP existante |
| Base analytique | BigQuery `cdp_marketing` | Source de vérité reporting |
| Anti-bot | Honeypot + timing check + rate limiting n8n | Sans friction UX (pas de CAPTCHA visible) |
| Validation email | Format regex + vérification MX (API externe) | Qualité donnée sans bloquer l'inscription |
| Validation SN | Regex par marque/famille, non-bloquante | Flexibilité + alertes internes |
| Consentement | Double : newsletter opt-in + privacy obligatoire | RGPD |
| Extension garantie | SFMC journey (communication d'abord) | Valider intérêt avant process commercial |

---

## Flux

```
Musicien
    │
    └── form/index.html  (landing page HTML autonome)
                │  POST webhook
                ▼
        n8n : instrument_registration_workflow.json
                │
                ├── Anti-bot (honeypot + timing)     → rejet silencieux si bot
                ├── Sanitize & Normalize              → clean email, SN, country ISO
                ├── Email DNS check (API validation)  → flag email_valid
                ├── SN Format check (regex)           → flag sn_format_valid
                ├── BQ Check Duplicate               → si doublon : email "déjà enregistré" + STOP
                ├── PG Upsert Contact                → marketing.contacts (COALESCE non-destructif)
                ├── PG Upsert Subscription           → uniquement si marketing_consent = true
                ├── BQ Insert Registration           → cdp_marketing.instrument_registrations
                └── Email confirmation               → si consent : déclencher journey SFMC garantie
```

---

## BigQuery

- **Projet** : `buffet-crampon-data`
- **Dataset** : `cdp_marketing`
- **Table** : `instrument_registrations`
- **Location** : `europe-west9`
- **Partitionnement** : sur `submitted_at` (réduction coûts requêtes)

| Fichier | Rôle |
|---|---|
| `bigquery/schema_instrument_registrations.json` | Schema BQ complet |
| `bigquery/create_table.py` | Script Python création de la table |
| `n8n/queries_bigquery.md` | Requêtes SQL utilisées par le workflow n8n |

---

## PostgreSQL CDP (OVH VPS)

Tables impactées dans le schéma `marketing` :

| Table | Action | Règle |
|---|---|---|
| `marketing.contacts` | UPSERT | COALESCE — ne jamais écraser une donnée existante par une valeur vide |
| `marketing.contact_brand_subscriptions` | INSERT (si consent) | Uniquement si `marketing_consent = true` — sinon 0 ligne, aucune erreur |

---

## Validation & Qualité donnée

### Anti-bot
- **Honeypot** : champ caché `website` dans le formulaire — si rempli → `bot_score = 1`, rejet silencieux (200 renvoyé)
- **Timing** : soumission < 3 secondes → `bot_score = 0.8`, flaggé mais pas rejeté
- **Rate limiting** : même IP > 3 soumissions / heure → blocage dans n8n

### Email
- Format : regex RFC 5322
- Domaine : vérification MX record (API externe — Abstract API ou Bouncer)
- Résultat stocké dans `email_valid` — non-bloquant, exclut des envois SFMC si `false`

### Numéro de série
Formats à confirmer avec le service produit / AX :

| Marque | Famille | Pattern attendu (à valider) |
|---|---|---|
| Buffet Crampon | Clarinette | `[A-Z]{1,2}[0-9]{5,6}` |
| Besson | Cuivres | `[0-9]{6,8}` |
| Powell Flutes | Flûte | `[0-9]{5}[A-Z]?` |
| B&S | Cuivres | À définir |
| Antoine Courtois | Cuivres | À définir |

- Saisie brute stockée dans `serial_number_raw` (jamais modifiée)
- Version normalisée dans `serial_number` (uppercase, trim)
- Résultat dans `sn_format_valid` — non-bloquant, alerte interne si `false`

### Déduplication
- Même `email + serial_number` déjà enregistré → `is_duplicate = true`, aucun doublon BQ créé
- Email de notification "instrument déjà enregistré" envoyé au musicien

---

## Structure des fichiers

```
formulaire-enregistrement/
├── CLAUDE.md                                      ← CE FICHIER
├── bigquery/
│   ├── schema_instrument_registrations.json       ← Schema BQ complet
│   └── create_table.py                            ← Script Python création table (à créer)
├── n8n/
│   ├── queries_bigquery.md                        ← Requêtes SQL de référence
│   └── instrument_registration_workflow.json      ← Workflow n8n (à exporter après build)
├── form/
│   └── index.html                                 ← Formulaire HTML autonome (à créer)
├── email/
│   └── confirmation.html                          ← Email de confirmation (à créer)
└── data/
    ├── README.md                                  ← Instructions catalogue AX
    └── instruments_catalog.csv                    ← Catalogue AX marques/familles/modèles (à remplir)
```

---

## Décommission NFT

| Élément | Action | Statut |
|---|---|---|
| Workflow n8n `nft_registration_workflow` | Désactiver dans n8n (garder en archive) | ⬜ À faire |
| Formulaire `NFT/form/index.html` | Retirer de la prod | ⬜ À faire |
| Table BQ `nft_registrations` | Conserver en lecture seule (données historiques) | ⬜ À confirmer |
| Table BQ `nft_instruments` | Archiver | ⬜ À confirmer |
| Dossier `NFT/` (bc-stack) | Déplacer dans `_archive/` après mise en prod | ⬜ Après mise en prod |

---

## Blockers actuels

- [ ] **Catalogue AX** — liste des marques, familles, modèles, formats SN (Guillaume récupère depuis AX)
- [ ] **RGPD** — revue juridique du texte de consentement avant mise en prod
- [ ] **Extension garantie** — décision : communication email SFMC uniquement, ou process commercial Stripe ?

---

## Liens utiles

| Ressource | Lien / Localisation |
|---|---|
| BigQuery console | `buffet-crampon-data` → `cdp_marketing` |
| n8n instance | VPS OVH (workflows → instrument_registration) |
| Formulaire NFT (référence) | `NFT/form/index.html` |
| Workflow NFT (référence) | `NFT/n8n/nft_registration_workflow.json` |
| Schema NFT (référence) | `NFT/bigquery/schema_nft_registrations.json` |
| Reporting config BQ | `Reporting/reporting_config.md` |
