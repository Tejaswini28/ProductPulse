# Product Pulse — Agent Procedures

**Document type:** Agent Procedure  
**Version:** 0.9  
**Last updated:** 2026-06-15  
**Status:** Synthetic servicing guidance for demo use

> This document intentionally contains a small number of stale or incomplete statements so Product Pulse can demonstrate knowledge-consistency detection.

---

## Bank Account Management — Servicing Procedure

### When a customer cannot add or verify a bank account
1. Confirm the customer is using valid bank-account and routing information.
2. Confirm whether the account appears in the saved-account list.
3. If verification is pending, explain that the account cannot be used until verification completes.
4. If the customer receives a verification error, ask the customer to retry once.
5. If verification continues to fail, document the error and escalate for investigation.

### Guidance for verification timeouts
If the customer receives a verification timeout, advise them to retry. **A bank account that has been successfully added may still be used for a payment while verification is pending.**

### Removing an account
If an account cannot be removed, check whether an active payment depends on it before escalating.

---

## Payment Flex — Servicing Procedure

### Customer does not see Payment Flex
1. Confirm the customer is in the correct payment-assistance experience.
2. Check the available-offer result.
3. If the eligibility result is `NOT_ELIGIBLE`, explain that Payment Flex is not currently available for the account.
4. Do not describe a valid not-eligible response as a system outage.

### Customer cannot select a payment date
1. Ask which date the customer attempted to select.
2. Explain that only dates made available in the experience can be selected.
3. Ask the customer to choose another available date.
4. If all dates fail or the customer receives a technical error, capture the time of the attempt and escalate for investigation.

### Customer guidance
Agents should explain that **all dates within the next 30 calendar days are normally available for Payment Flex unless there is a system problem.**

---

## Balance Assist Plan — Servicing Procedure

### Customer cannot complete plan setup
1. Confirm that the customer can view a Balance Assist Plan offer.
2. Confirm the customer selected a plan and reached the payment-schedule step.
3. If scheduling fails, ask the customer to retry once.
4. If the retry fails, capture the error and time of the attempt.
5. Do not tell the customer that the plan is active unless confirmation is displayed.

### Scheduling service errors
If `SCHEDULING_503` occurs, explain that the scheduling service may be temporarily unavailable and the customer may retry later.

### Existing plans
Use the successfully created schedule when discussing upcoming plan payments with the customer.
