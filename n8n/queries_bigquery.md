# Queries — Workflow Instrument Registration
# Ordre d'apparition dans le workflow n8n.
# Les queries PG et BQ sont intégrées dans le JSON du workflow.
# Ce fichier sert de référence pour vérification / copie manuelle si besoin.

---

## PostgreSQL (CDP — OVH VPS)

### Node : PG Upsert Contact
> Crée ou met à jour le contact. COALESCE = ne jamais écraser une valeur existante par une valeur vide.
> RETURNING contact_id dans tous les cas (nouveau ou existant).

```sql
INSERT INTO marketing.contacts
  (email, first_name, last_name, phone,
   country_code, language_code,
   newsletter_source, contact_status,
   first_contact_date, created_at, updated_at)
VALUES (
  '{{ $json.email }}',
  '{{ $json.first_name }}',
  '{{ $json.last_name }}',
  '{{ $json.phone }}',
  '{{ $json.country_code }}',
  '{{ $json.browser_language }}',
  'instrument_registration',
  'cold_lead',
  NOW(), NOW(), NOW()
)
ON CONFLICT (email) DO UPDATE SET
  first_name    = COALESCE(NULLIF(EXCLUDED.first_name, ''),    marketing.contacts.first_name),
  last_name     = COALESCE(NULLIF(EXCLUDED.last_name, ''),     marketing.contacts.last_name),
  phone         = COALESCE(NULLIF(EXCLUDED.phone, ''),         marketing.contacts.phone),
  country_code  = COALESCE(NULLIF(EXCLUDED.country_code, ''),  marketing.contacts.country_code),
  language_code = COALESCE(NULLIF(EXCLUDED.language_code, ''), marketing.contacts.language_code),
  updated_at    = NOW()
RETURNING contact_id
```

---

### Node : PG Upsert Subscription
> Insère uniquement si marketing_consent = true.
> Si consent = false : 0 lignes insérées, aucune erreur, aucune subscription créée.

```sql
INSERT INTO marketing.contact_brand_subscriptions
  (contact_id, brand, is_active, optin_date, optin_source, created_at, updated_at)
SELECT
  '{{ $json.contact_id }}',
  '{{ $json.brand }}',
  true,
  NOW(),
  'instrument_registration',
  NOW(),
  NOW()
WHERE {{ $json.marketing_consent }} = true
ON CONFLICT (contact_id, brand) DO UPDATE SET
  is_active    = true,
  optin_date   = NOW(),
  optin_source = 'instrument_registration',
  updated_at   = NOW()
```

---

## BigQuery
> Location : `europe-west9` sur chaque node BQ
> Projet : `buffet-crampon-data`
> Dataset : `cdp_marketing`

---

### Node : BQ Check Duplicate

```sql
SELECT COUNT(*) AS cnt
FROM `buffet-crampon-data.cdp_marketing.instrument_registrations`
WHERE serial_number = '{{ $json.serial_number }}'
  AND email = '{{ $json.email }}'
```

---

### Node : BQ Insert Registration

```sql
INSERT INTO `buffet-crampon-data.cdp_marketing.instrument_registrations`
  (registration_id, contact_id, email, first_name, last_name, phone,
   address_line1, address_line2, city, state, zip, country_code,
   brand, instrument_family, instrument_model,
   serial_number_raw, serial_number, sn_format_valid,
   dealer_name, purchase_date,
   marketing_consent, privacy_accepted,
   consent_ip, consent_timestamp,
   submission_source, browser_language,
   email_valid, is_duplicate, bot_score,
   warranty_offer_sent,
   submitted_at)
VALUES (
  '{{ $json.registration_id }}',
  '{{ $json.contact_id }}',
  '{{ $json.email }}',
  '{{ $json.first_name }}',
  '{{ $json.last_name }}',
  '{{ $json.phone }}',
  '{{ $json.address_line1 }}',
  '{{ $json.address_line2 }}',
  '{{ $json.city }}',
  '{{ $json.state }}',
  '{{ $json.zip }}',
  '{{ $json.country_code }}',
  '{{ $json.brand }}',
  '{{ $json.instrument_family }}',
  '{{ $json.instrument_model }}',
  '{{ $json.serial_number_raw }}',
  '{{ $json.serial_number }}',
  {{ $json.sn_format_valid }},
  '{{ $json.dealer_name }}',
  {{ $json.purchase_date ? `'${$json.purchase_date}'` : 'NULL' }},
  {{ $json.marketing_consent }},
  {{ $json.privacy_accepted }},
  '{{ $json.consent_ip }}',
  CURRENT_TIMESTAMP(),
  '{{ $json.submission_source }}',
  '{{ $json.browser_language }}',
  {{ $json.email_valid }},
  {{ $json.is_duplicate }},
  {{ $json.bot_score }},
  false,
  CURRENT_TIMESTAMP()
)
```

---

### Node : BQ Update Warranty Sent
> Déclenché par le workflow SFMC après envoi de l'email d'offre garantie.

```sql
UPDATE `buffet-crampon-data.cdp_marketing.instrument_registrations`
SET
  warranty_offer_sent    = true,
  warranty_offer_sent_at = CURRENT_TIMESTAMP()
WHERE registration_id = '{{ $json.registration_id }}'
```

---

## Requêtes reporting (Looker Studio / n8n)

### Inscriptions par semaine et par marque

```sql
SELECT
  DATE_TRUNC(submitted_at, WEEK) AS week,
  brand,
  COUNT(*) AS registrations,
  COUNTIF(marketing_consent = true) AS with_consent,
  COUNTIF(email_valid = false) AS invalid_emails,
  COUNTIF(is_duplicate = true) AS duplicates,
  COUNTIF(bot_score >= 0.8) AS suspected_bots
FROM `buffet-crampon-data.cdp_marketing.instrument_registrations`
WHERE submitted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY 1, 2
ORDER BY 1 DESC, 2
```

### Taux de consentement par pays

```sql
SELECT
  country_code,
  COUNT(*) AS total,
  COUNTIF(marketing_consent = true) AS opted_in,
  ROUND(COUNTIF(marketing_consent = true) / COUNT(*) * 100, 1) AS consent_rate_pct
FROM `buffet-crampon-data.cdp_marketing.instrument_registrations`
WHERE submitted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  AND is_duplicate = false
  AND bot_score < 0.8
GROUP BY 1
HAVING total >= 10
ORDER BY consent_rate_pct DESC
```
