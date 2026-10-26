# Verification and pricing

Implemented in `backend/app/verification/rules.py`, `pricing/engine.py`, `pricing/pipeline.py`; all deterministic and unit-tested. No AI confidence score is used anywhere in these decisions.

## Product matching

Compared against the user-confirmed identity. Per attribute the result is `match`, `mismatch` or `not_stated`.

Medicine (checked when the identity has the value): active ingredient(s), strength, dosage form, brand; plus pack size, barcode, manufacturer.

- **Ingredients**: compared as sets; salt words (HCl, sodium, …) are ignored; `+ / , & and` separate ingredients.
- **Strength**: parsed to (value, unit) pairs; g/kg/mcg → mg and L → mL before comparison. From a listing title, the identity's strengths must appear (a different strength is a mismatch).
- **Dosage form**: base form plus release qualifiers. `film coated` is ignored; `extended/sustained/modified release`, `chewable`, `dispersible`, `ODT` etc. **must match**.
- **Brand**: a different stated brand is a mismatch. A brand missing from the listing is `not_stated`, which blocks `VERIFIED`. Different brands are never equivalent.
- **Barcode**: both stated and different → mismatch. **Manufacturer** difference only downgrades to `PARTIALLY_VERIFIED`.
- **Pack size**: equal → match; both known but different → *comparable by unit price* (not a mismatch); unknown on either side → `not_stated`.

Supplies/equipment: product name tokens, model/SKU, size, material, sterility (when the identity has them), plus pack size.

## Verification statuses

| Status | Criteria (all must hold) |
|---|---|
| `REJECTED` | Any critical attribute explicitly **mismatches**, barcode differs, or the price is ≤ 0. |
| `UNVERIFIED` | Not rejected, and any of: no direct (API/page) price evidence (search snippets never count); price or currency missing; direct evidence does not support the stated price or conflicts (price/currency differ beyond 0.5%); `priceValidUntil` has passed; **demonstration data** (always capped here). |
| `PARTIALLY_VERIFIED` | Not rejected, direct evidence supports the price, but at least one: a required attribute is not stated; evidence is older than `OFFER_MAX_AGE_HOURS`; no product URL/API reference to re-check; manufacturer differs; pack size unknown. |
| `VERIFIED` | Direct evidence supports the price, evidence is fresh, a source URL/API reference exists, no conflicts, and every required attribute is explicitly `match` (pack size match or known-but-different). |

Principles: a successful HTTP response is not proof; supplier claims are not independent proof of legitimacy (`supplier_verification` is always `not_independently_verified`); conflicts are preserved in `verification.conflicts` and downgrade the offer; missing data stays missing (`verification.missing`); rejected offers keep their evidence. `VERIFIED` means **source-verified**, not "safe to buy".

Each result lists `reasons` and a `checks[]` array (`name`, `result` = pass/fail/missing/conflict/info, `detail`).

## Pricing (all values kept separate)

| Field | Meaning |
|---|---|
| `pack_price_original`, `currency_original` | Supplier selling price as stated |
| `pack_price` | Converted to the market currency (`INR` for India, `USD` for Global by default), or `null` if no rate |
| `mrp` | MRP/list price, **separate** from the selling price (a note flags selling price above MRP) |
| `unit_price` | `pack_price / offer_pack_units` |
| `requested_units` / `packs_needed` | `quantity × identity units`; `ceil(requested / offer pack units)` |
| `requested_cost` | billed packs × pack price; includes MOQ and **source-provided** quantity breaks only |
| `shipping_cost`, `tax_status`, `tax_amount` | Only when the source states them |
| `estimated_known_total` | requested cost + known shipping + known added tax |
| `total_is_complete` | true only if shipping is known and tax is `included` or `added` |
| `exclusions` | What the total leaves out (e.g. "Shipping not stated") |
| `final_payable` | Set **only** when the source itself states a checkout total, else `null` |

Rules: exchange rates come from the configured provider (`none` default → no conversion; `static`; `frankfurter`) with the rate, source and observation time recorded; there is no invented rate, and an unconverted offer keeps its original currency, is flagged and is not ranked. `comparability` is `same_pack`, `pack_differs` (compared via unit price) or `unknown_pack` (no comparable cost). MOQ raises the billed quantity and is noted; no discount is applied unless the source supplied a break. An incomplete total is never labelled final payable.

Reference ceiling prices (optional CSV) only add a note when the unit price exceeds the ceiling in the same currency.

## Eligibility and ranking

Ineligible (shown, never ranked, reason given): rejected; business-only listing in retail mode; out of stock; no price; price not convertible; no comparable cost; outside the user's min/max price (per pack, converted; filters apply only when set; if the price cannot be evaluated the offer is ineligible). Unknown stock stays `unknown` and eligible.

Sort order: eligible first, then verification tier (verified → partial → unverified → rejected), then requested cost, then unit price, then supplier name. The UI shows tiers as tabs, so partially verified and unverified offers are viewed separately and the default tab is *Source-verified* (or the first non-empty tab). Ranking is by supplier price for the requested quantity (before shipping and tax) because shipping/tax are often unknown; other sort keys (unit price, known total, observed time) are available in the table.

## Deduplication

Offers merge only when supplier key (domain or normalised name), canonical listing key (URL without tracking parameters/fragment, else normalised title) **and pack size** all match. Different suppliers or pack sizes are never merged. Evidence is unioned, so conflicting observations of the same listing downgrade it instead of being hidden.

## Retail vs business

Retail: individual packs, known delivery charges, listed vs checkout price distinction, business-only listings excluded. Business: requested pack count, MOQ column, source-provided quantity breaks, lead time and credit terms shown **only if a source stated them**, quote/enquiry links where supplied. No checkout, payment or ordering exists in either mode.
