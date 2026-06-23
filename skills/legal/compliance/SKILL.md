# Compliance

## Privacy Regulation Quick Reference

| Regulation    | Jurisdiction     | DSR Response Time                 | Extension      | Key Differentiator                                                                 |
| ------------- | ---------------- | --------------------------------- | -------------- | ---------------------------------------------------------------------------------- |
| **GDPR**      | EU/EEA           | 30 days                           | +60 days       | Lawful basis required; 72-hour breach notification; DPIAs for high-risk processing |
| **CCPA/CPRA** | California       | 45 calendar days (10 biz day ack) | +45 days       | Opt-out of sale/sharing; sensitive PI use limits (CPRA)                            |
| **UK GDPR**   | United Kingdom   | 30 days                           | +60 days       | Post-Brexit UK version; ICO oversight                                              |
| **LGPD**      | Brazil           | 15 days                           | Limited        | DPO required; ANPD enforcement                                                     |
| **PIPL**      | China            | Per regulation                    | Per regulation | Strict cross-border rules; data localization; CAC oversight                        |
| **PIPEDA**    | Canada (federal) | 30 days                           | Per regulation | Consent-based; OPC oversight                                                       |
| **POPIA**     | South Africa     | 30 days                           | Per regulation | Information Regulator; required registration                                       |
| **PDPA**      | Singapore        | 30 days                           | Per regulation | Do Not Call registry; PDPC enforcement                                             |

## DPA Review Checklist

### Required Elements (GDPR Article 28)

- Subject matter, duration, nature, and purpose of processing
- Types of personal data and categories of data subjects
- Controller obligations, rights, and documented instructions

### Processor Obligations

- Process only on documented instructions
- Personnel bound to confidentiality
- Appropriate technical and organizational security measures (Article 32)
- Sub-processor controls: written authorization, change notification with right to object, flow-down obligations, processor remains liable
- Assist with DSR responses, security, breach notification, DPIAs
- Delete or return all data on termination (controller's choice)
- Audit rights (or accept SOC 2 Type II + right to audit on cause)
- Breach notification without undue delay (target 24-48 hours to enable controller's 72-hour regulatory deadline)

### International Transfers

- Valid transfer mechanism identified (SCCs, adequacy decision, BCRs)
- Current EU SCCs (June 2021 version) with correct module (C2P, C2C, P2P, P2C)
- Transfer impact assessment completed for non-adequacy countries
- Supplementary measures documented
- UK International Data Transfer Addendum included if UK data in scope

### Common DPA Red Flags

| Issue                                           | Risk                                       | Standard Position                       |
| ----------------------------------------------- | ------------------------------------------ | --------------------------------------- |
| Blanket sub-processor auth without notification | Loss of control over processing chain      | Require notification + right to object  |
| Breach notification > 72 hours                  | May prevent timely regulatory notification | Require 24-48 hours                     |
| No audit rights                                 | Cannot verify compliance                   | SOC 2 Type II + audit on cause          |
| No deletion timeline                            | Data retained indefinitely                 | Delete within 30-90 days of termination |
| No processing locations specified               | Data processed anywhere                    | Require location disclosure             |
| Outdated SCCs                                   | Invalid transfer mechanism                 | Require 2021 EU SCCs                    |

## DSR Exemptions to Check Before Fulfillment

- Legal claims defense or establishment
- Legal obligations requiring retention
- Litigation hold on relevant data
- Regulatory retention periods (financial, employment records)
- Public interest or official authority
- Freedom of expression (erasure requests)
- Third-party rights adversely affected

## Escalation Criteria

- New regulation directly affects core business activities
- Enforcement action in the organization's sector signals heightened scrutiny
- Compliance deadline approaching that requires organizational changes
- Data transfer mechanism the organization relies on is challenged or invalidated
- Regulatory authority initiates inquiry or investigation involving the organization

## Gotchas

- **72-hour breach clock starts at "awareness"** -- GDPR's 72 hours runs from when the processor became aware, not when they notified you; a DPA allowing processor notification "within 72 hours" leaves you zero time for regulatory filing.
- **SCCs module selection matters** -- using the wrong SCC module (e.g., C2C instead of C2P) can invalidate the entire transfer mechanism even if the rest of the DPA is perfect.
- **"Legitimate interest" is not a blank check** -- GDPR requires a documented balancing test (LIA) for each processing activity relying on legitimate interest; many organizations skip this and get caught in audits.
- **CPRA's sensitive PI category is broader than GDPR's special categories** -- it includes SSN, financial account info, precise geolocation, and union membership, which catch teams that only map to GDPR categories.
- **Sub-processor liability survives contract termination** -- the processor remains liable for sub-processor acts even after the main agreement ends; termination provisions that release the processor from sub-processor obligations are a trap.