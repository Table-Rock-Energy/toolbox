# Data Enrichment Service Exploration

## Objective

Evaluate third-party APIs that can take a validated **name + address** (as produced by our Extract, Title, and Proration tools) and return enriched contact and demographic data:

- **Phone numbers** (up to 5 — mobile, landline, VoIP)
- **Email addresses**
- **Social media profile links**
- **Demographic flags**: deceased status, bankruptcy filings, liens/judgments

---

## Service Comparison

### Tier 1: All-in-One (Contact + Public Records)

These services cover both contact enrichment *and* public records (deceased, bankruptcy, liens) in a single API.

#### SearchBug

| Attribute | Detail |
|-----------|--------|
| **Website** | [searchbug.com/api](https://www.searchbug.com/api/default.aspx) |
| **Input** | Name, address, phone, email, SSN |
| **Contact output** | Full name, aliases, current + previous addresses, all known phone numbers (with type: wireless/landline), email |
| **Public records output** | Date of death (if deceased), bankruptcies, liens, judgments, criminal records, AML watchlist |
| **Social media** | Not included natively |
| **Format** | REST API, JSON and XML responses |
| **Pricing model** | Pay-per-query, no contracts, no minimums |
| **Key prices** | People Search: $0.30–$0.77/hit; Background Report: $5–$17/hit; AML Watchlist: $0.05/hit; Email verify: $0.003/hit |
| **Free tier** | Sandbox test account with limited live queries |
| **Fit** | Strong for deceased + bankruptcy + liens + phones. No social media. Very transparent pricing. |

#### Tracers

| Attribute | Detail |
|-----------|--------|
| **Website** | [tracers.com/api](https://www.tracers.com/api/) |
| **Input** | Name, address, phone, email |
| **Contact output** | Phone numbers, addresses, employment records, relatives |
| **Public records output** | Deceased records, bankruptcies, liens/judgments, criminal records, property records |
| **Social media** | Not included |
| **Format** | REST API |
| **Pricing model** | Per-search or monthly unlimited tiers; starts ~$39/month |
| **Free tier** | No public free tier |
| **Fit** | Broadest public records coverage (120B+ records). Good for all demographic flags. Pricing requires sales contact. |

#### Pipl

| Attribute | Detail |
|-----------|--------|
| **Website** | [docs.pipl.com](https://docs.pipl.com/) |
| **Input** | Name, email, phone, address, social username |
| **Contact output** | Phone numbers (mobile + landline), email addresses, addresses |
| **Public records output** | Limited — focused on identity resolution, not public records |
| **Social media** | Yes — Facebook, Twitter/X, LinkedIn, and 400+ networks |
| **Format** | REST API, JSON |
| **Pricing model** | Custom; $500/month minimum |
| **Response time** | 5–7 seconds per query |
| **Fit** | Best social media coverage. 3B+ identity index. Weak on bankruptcy/liens. |

---

### Tier 2: Contact Enrichment Only (Phone, Email, Social)

These excel at contact data but do **not** provide public records (deceased/bankruptcy/liens).

#### People Data Labs (PDL)

| Attribute | Detail |
|-----------|--------|
| **Website** | [peopledatalabs.com](https://www.peopledatalabs.com/person-data) |
| **Input** | Name + location/company, email, phone, LinkedIn URL |
| **Contact output** | Phones, emails, addresses, job history, education |
| **Social media** | LinkedIn, Twitter/X, Facebook, GitHub |
| **Format** | REST API, JSON; bulk API available |
| **Pricing** | Free: 100 lookups/mo (no contact data); Pro: $98/mo for 350 credits (~$0.28/query); Enterprise: ~$2,500+/mo |
| **Charging** | Per match only — no charge on 404 (miss) |
| **Coverage** | 1.5B+ person profiles, 200+ countries |
| **Fit** | Best price-to-coverage ratio. Good phone + email + social. No public records. |

#### FullContact

| Attribute | Detail |
|-----------|--------|
| **Website** | [fullcontact.com](https://www.fullcontact.com/) |
| **Input** | Email, phone, name + location, social handles |
| **Contact output** | Emails, phones, addresses |
| **Social media** | Yes — cross-channel identity graph, social handles |
| **Format** | REST API, JSON |
| **Pricing** | Free: 100 enrichments; Pro: $99/mo; Premium: $500/mo; Enterprise: $2,000+/mo |
| **Response time** | ~2.4 seconds |
| **Coverage** | 200+ countries, 91% cross-device match accuracy |
| **Fit** | Good identity resolution. Privacy-safe. Moderate pricing. |

#### Swordfish AI

| Attribute | Detail |
|-----------|--------|
| **Website** | [swordfish.ai](https://swordfish.ai/) |
| **Input** | Name, company, email, phone, social profile |
| **Contact output** | Cell phones, personal emails, business emails |
| **Social media** | LinkedIn, Facebook, Twitter/X, GitHub, Stack Overflow |
| **Format** | REST API + Chrome extension + bulk CSV upload |
| **Pricing** | $99/mo unlimited mobiles and emails; custom API plans for higher volume |
| **Accuracy** | Claims 95% for emails and phone numbers |
| **Fit** | Simplest pricing (flat rate). Good for phone-heavy use cases. No public records. |

---

### Tier 3: Public Records / Legal Only (Bankruptcy, Liens, Deceased)

These specialize in court and public records data only — no contact enrichment.

#### Epiq (AACER) Bankruptcy API

| Attribute | Detail |
|-----------|--------|
| **Website** | [epiqglobal.com](https://www.epiqglobal.com/en-us/services/bankruptcy-and-trustee-services/bankruptcy-services/api-integrations) |
| **Data** | Real-time bankruptcy case data from all US courts |
| **Format** | REST API, system-to-system |
| **Fit** | Deep bankruptcy-only data. Overkill if you just need a yes/no flag. |

#### CourtListener (RECAP / PACER)

| Attribute | Detail |
|-----------|--------|
| **Website** | [courtlistener.com](https://www.courtlistener.com/help/api/rest/v3/pacer/) |
| **Data** | Federal bankruptcy dockets, parties, filings from PACER |
| **Format** | REST API, JSON |
| **Pricing** | Free (nonprofit project by Free Law Project) |
| **Fit** | Free bankruptcy court data. Requires matching logic on your end. |

#### Dun & Bradstreet (D&B Direct)

| Attribute | Detail |
|-----------|--------|
| **Website** | [docs.dnb.com](https://docs.dnb.com/direct/2.0/en-US/publicrecord/latest/orderproduct/bankruptcy-rest-API) |
| **Data** | Suits, liens, judgments, bankruptcies (US + Canada) |
| **Format** | REST API |
| **Pricing** | Enterprise; contact sales |
| **Fit** | Business-focused public records. Expensive. Better for company enrichment. |

---

## Recommendation Matrix

### By data need:

| Need | Best option | Runner-up |
|------|-------------|-----------|
| **Phone numbers (up to 5)** | SearchBug ($0.30–$0.77/hit) | PDL ($0.28/hit) |
| **Email addresses** | PDL ($0.28/hit) | Swordfish ($99/mo flat) |
| **Social media links** | Pipl ($500/mo min) | PDL ($0.28/hit) |
| **Deceased flag** | SearchBug ($0.30–$0.77/hit) | Tracers (~$39+/mo) |
| **Bankruptcy flag** | SearchBug ($5–$17/hit background) | Tracers (~$39+/mo) |
| **Liens/Judgments** | SearchBug ($5–$17/hit background) | Tracers (~$39+/mo) |

### Recommended integration strategies:

#### Option A: Two-API approach (recommended)

1. **People Data Labs** — for phone, email, and social media enrichment ($98/mo for 350 lookups)
2. **SearchBug** — for deceased, bankruptcy, and liens ($0.30–$0.77 per people search + $5–$17 for full background)

**Why:** Cleanest separation of concerns. PDL has the best developer experience and coverage for contact data. SearchBug has transparent per-query pricing for public records with no minimums. Both are REST/JSON APIs that integrate directly into a FastAPI backend.

**Estimated cost for 100 enrichments/month:**
- PDL: ~$28 (100 × $0.28)
- SearchBug people search: ~$50 (100 × $0.50 avg)
- SearchBug background (if needed): ~$1,000 (100 × $10 avg)
- **Total: ~$78–$1,078/month** depending on depth

#### Option B: Single-API approach (simpler)

1. **SearchBug** only — covers phones, emails (via people search), deceased, bankruptcy, liens

**Why:** One vendor, one integration. Their People Search API returns phones, addresses, aliases, DOB, and death date. Background Report adds bankruptcy, liens, judgments. Missing piece: social media links (not available).

**Estimated cost for 100 enrichments/month:**
- People search: ~$50 (100 × $0.50)
- Background reports: ~$1,000 (100 × $10)
- **Total: ~$50–$1,050/month**

#### Option C: Premium all-in-one

1. **Pipl** — phones, emails, social media, basic identity verification ($500/mo minimum)
2. **Tracers** — deceased, bankruptcy, liens (~$39+/mo)

**Why:** Best data quality and broadest social media coverage. Higher cost floor.

**Estimated cost: $539+/month minimum**

---

## Integration Architecture

```
┌─────────────────────┐
│  Extract / Title /  │
│  Proration results  │
│  (name + address)   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Enrichment Service │  ← new backend/app/services/enrichment/
│  (orchestrator)     │
└────┬──────────┬─────┘
     │          │
     ▼          ▼
┌─────────┐ ┌──────────┐
│  PDL /  │ │SearchBug │
│ Contact │ │ / Public │
│   API   │ │ Records  │
└─────────┘ └──────────┘
     │          │
     ▼          ▼
┌─────────────────────┐
│  Unified enrichment │
│  response model     │
│  (Pydantic)         │
└─────────────────────┘
```

### Proposed backend structure

```
backend/app/services/enrichment/
├── __init__.py
├── enrichment_service.py    # Orchestrator: calls contact + records APIs
├── contact_provider.py      # Abstract base + PDL implementation
├── records_provider.py      # Abstract base + SearchBug implementation
└── models.py                # EnrichedPerson, PhoneNumber, SocialProfile, etc.

backend/app/api/
└── enrichment.py            # POST /api/enrichment/lookup
```

### Proposed Pydantic models

```python
class PhoneNumber(BaseModel):
    number: str
    type: str | None = None        # mobile, landline, voip
    carrier: str | None = None

class SocialProfile(BaseModel):
    platform: str                   # linkedin, twitter, facebook, etc.
    url: str
    username: str | None = None

class PublicRecordFlags(BaseModel):
    is_deceased: bool = False
    deceased_date: str | None = None
    has_bankruptcy: bool = False
    bankruptcy_details: list[str] = []
    has_liens: bool = False
    lien_details: list[str] = []

class EnrichedPerson(BaseModel):
    original_name: str
    original_address: str | None = None
    phones: list[PhoneNumber] = []          # up to 5
    emails: list[str] = []
    social_profiles: list[SocialProfile] = []
    public_records: PublicRecordFlags = PublicRecordFlags()
    enrichment_sources: list[str] = []      # which APIs contributed
    enriched_at: str                        # ISO timestamp
```

---

## Next Steps

1. **Sign up for sandbox/free accounts** with SearchBug and People Data Labs to test data quality against real names/addresses from our tools
2. **Evaluate match rates** — run 20–50 sample names+addresses through each API and measure hit rates
3. **Decide on depth** — determine whether basic people search (phones + deceased flag) is sufficient or if full background reports (bankruptcy + liens) are needed for every record
4. **Build the enrichment service** behind a feature flag so it can be enabled per-tool
5. **Add UI** — likely a new column/panel in the results tables with an "Enrich" button per row or a bulk "Enrich All" action

---

## Sources

- [People Data Labs — Person Data](https://www.peopledatalabs.com/person-data)
- [People Data Labs — Pricing](https://www.peopledatalabs.com/pricing/person)
- [SearchBug — API Services](https://www.searchbug.com/api/default.aspx)
- [SearchBug — API Pricing](https://www.searchbug.com/pricing-api.aspx)
- [Tracers — API Integration](https://www.tracers.com/api/)
- [Pipl — API Documentation](https://docs.pipl.com/)
- [FullContact](https://www.fullcontact.com/)
- [Swordfish AI](https://swordfish.ai/)
- [Epiq (AACER) Bankruptcy API](https://www.epiqglobal.com/en-us/services/bankruptcy-and-trustee-services/bankruptcy-services/api-integrations)
- [CourtListener PACER API](https://www.courtlistener.com/help/api/rest/v3/pacer/)
- [D&B Direct — Bankruptcy API](https://docs.dnb.com/direct/2.0/en-US/publicrecord/latest/orderproduct/bankruptcy-rest-API)
- [Coefficient — Top Data Enrichment APIs](https://coefficient.io/top-data-enrichment-apis)
- [Nubela — Best Data Enrichment APIs](https://nubela.co/blog/best-data-enrichment-apis/)
