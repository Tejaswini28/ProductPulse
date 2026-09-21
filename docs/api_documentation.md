# Product Pulse — API Documentation

**Document type:** API Documentation  
**Version:** 1.0  
**Last updated:** 2026-09-01

> Synthetic demo document. All APIs, responses, and error codes are fictional.

---

## 1. Bank Account API

**Used by:** Bank Account Management  
**Purpose:** Creates, retrieves, updates, and removes customer bank-account records.

### Key operations
- Add bank account
- Retrieve saved bank accounts
- Update bank-account display information
- Remove an eligible saved bank account

### Expected behavior
A successful add creates a bank-account record, but the account is not considered ready for payment until required verification succeeds.

### Example errors
- `BANK_ACCOUNT_INVALID` — submitted account information failed validation.
- `BANK_ACCOUNT_IN_USE` — account cannot currently be removed because an active payment depends on it.
- `BANK_ACCOUNT_500` — unexpected service failure.

---

## 2. Bank Verification API

**Used by:** Bank Account Management  
**Purpose:** Verifies newly added bank-account information before the account is made available for payments.

### Expected behavior
- `VERIFIED` means the bank account successfully completed verification.
- A verification failure or timeout must not be interpreted as successful verification.

### Example errors
- `BANK_VERIFY_TIMEOUT` — verification service did not return a result within the allowed time. Customer may retry later.
- `BANK_VERIFY_FAILED` — submitted account could not be verified.
- `BANK_VERIFY_UNAVAILABLE` — verification service is temporarily unavailable.

### Investigation note
A spike in `BANK_VERIFY_TIMEOUT` combined with lower Verification Success Rate may indicate service degradation rather than customer input error.

---

## 3. Customer Profile API

**Used by:** Bank Account Management, Payment Flex  
**Purpose:** Returns customer profile and account context needed to render supported experiences.

### Example errors
- `PROFILE_NOT_FOUND` — requested customer profile was not found.
- `PROFILE_TIMEOUT` — customer profile lookup timed out.

---

## 4. Offer Eligibility API

**Used by:** Payment Flex, Balance Assist Plan  
**Purpose:** Determines whether a customer qualifies for an assistance offer and returns applicable offer information.

### Expected responses
- `ELIGIBLE` — customer currently qualifies for an offer.
- `NOT_ELIGIBLE` — customer does not currently qualify. This is a valid business response, not a technical failure.

### Example errors
- `ELIGIBILITY_TIMEOUT` — eligibility request timed out.
- `ELIGIBILITY_500` — unexpected eligibility service error.

### Investigation note
When a session contains `NOT_ELIGIBLE` and API health is normal, an offer not being displayed may be expected product behavior.

---

## 5. Payment Scheduling API

**Used by:** Payment Flex, Balance Assist Plan  
**Purpose:** Validates payment-date selections and creates or manages scheduled payments associated with assistance products.

### Expected responses
- Available dates can be scheduled successfully when all relevant product rules are satisfied.
- `DATE_NOT_AVAILABLE` is a valid business response indicating that a selected date cannot be used. It does not necessarily indicate a technical failure.

### Example errors
- `DATE_NOT_AVAILABLE` — selected date is unavailable under current rules.
- `SCHEDULING_503` — scheduling service is temporarily unavailable.
- `SCHEDULING_500` — unexpected scheduling failure.

### Investigation note
Repeated `SCHEDULING_503` errors combined with a spike in API Error Rate and a drop in Scheduling Success Rate are evidence of likely service degradation.

---

## 6. Account Status API

**Used by:** Balance Assist Plan  
**Purpose:** Provides current account status and balance context used to support plan eligibility, presentation, and management.

### Example errors
- `ACCOUNT_STATUS_TIMEOUT` — account-status request timed out.
- `ACCOUNT_STATUS_UNAVAILABLE` — account-status service is temporarily unavailable.

### Investigation note
An isolated monitoring alert without confirmed customer impact should not automatically be classified as a customer-facing product issue.
