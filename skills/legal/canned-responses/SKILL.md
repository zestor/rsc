# Canned Responses

## Response Categories

| Category                     | Sub-types                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Data Subject Requests**    | Acknowledgment, identity verification, fulfillment (access/deletion/correction), partial denial, full denial, extension notice |
| **Discovery Holds**          | Initial hold notice, reminder/reaffirmation, scope modification, release                                                       |
| **Privacy Inquiries**        | Cookie/tracking, privacy policy, data sharing, children's data, cross-border transfer                                          |
| **Vendor Legal Questions**   | Contract status, amendment request, compliance certification, audit response, insurance certificate                            |
| **NDA Requests**             | Standard form send, counterparty markup acceptance, decline with explanation, renewal/extension                                |
| **Subpoena / Legal Process** | Acknowledgment, objection letter, extension request, compliance cover letter                                                   |
| **Insurance Notifications**  | Initial claim notification, supplemental information, reservation of rights response                                           |

## Escalation Triggers

### Universal (all categories)

- Potential litigation or regulatory investigation
- Inquiry from a regulator, government agency, or law enforcement
- Response could create a binding legal commitment or waiver
- Potential criminal liability
- Media attention involved or likely
- Unprecedented situation with no prior team handling
- Multiple jurisdictions with conflicting requirements
- Involves executive leadership or board members

### Category-Specific

**Data Subject Requests**: Request from/on behalf of a minor; data subject to litigation hold; requester in active litigation with org; employee with active HR matter; request scope appears to be a fishing expedition; involves special category data (health, biometric, genetic).

**Discovery Holds**: Potential criminal liability; unclear or disputed preservation scope; hold conflicts with regulatory deletion requirements; prior holds exist for related matters.

**Vendor Questions**: Vendor disputing contract terms or threatening litigation; response could affect ongoing negotiation; involves regulatory compliance beyond contract interpretation.

**Subpoena / Legal Process**: Always requires counsel review -- templates are starting frameworks only. Flag privilege issues, third-party data, cross-border production, and unreasonable timelines.

## Required Template Variables

Every generated response must be customized with:

- Correct names, dates, and reference numbers
- Specific facts of the situation
- Applicable jurisdiction and regulation
- Response deadlines calculated from receipt date
- Appropriate signature block and contact information

## Gotchas

- **Subpoena responses are never send-ready** -- they always require individualized counsel review regardless of how standard they appear.
- **Litigation holds override deletion requests** -- a DSR requesting deletion cannot be fulfilled if the data is subject to a legal hold; failing to catch this creates spoliation risk.
- **Jurisdiction changes timelines silently** -- GDPR gives 30 days, CCPA gives 45 calendar days, LGPD gives 15 days; using the wrong timeline can trigger regulatory penalties.
- **Privilege headers are not optional** -- discovery hold notices must include privilege markings (attorney-client communication); omitting them risks waiving privilege over the entire communication.
- **Stale templates create liability** -- templates citing superseded regulations or outdated timelines can be worse than no template at all.