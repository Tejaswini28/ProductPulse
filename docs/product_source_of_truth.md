# Product Pulse — Product Source of Truth

**Document type:** Product Source of Truth  
**Authority:** Authoritative for product behavior and business rules  
**Version:** 1.0  
**Last updated:** 2026-09-01  
**Products:** Bank Account Management, Payment Flex, Balance Assist Plan

> Synthetic demo document. All products, rules, customers, and operational details are fictional.

---

## 1. Bank Account Management

### Purpose
Bank Account Management allows customers to add, verify, view, update, select, and remove bank accounts used for payments.

### Core functionality
- Customers may add a checking or savings account by providing valid routing and account information.
- A newly added bank account must complete verification before it can be used for a payment.
- Customers may view saved bank accounts and update non-sensitive display information such as an account nickname.
- Customers may remove an eligible saved bank account.
- The experience uses customer-profile information to associate saved bank accounts with the correct customer.

### Expected behavior
- When valid account information is submitted, Bank Account API creates the bank-account record and Bank Verification API performs verification.
- A bank account remains unavailable for payment until verification succeeds.
- If verification is temporarily unavailable, the product should display an error and allow the customer to retry later.
- A verification service failure must not be represented to the customer as successful verification.

### Important rules
- Verification is required before first use of a newly added bank account.
- A pending or failed verification does not mean the bank account has been approved for payments.
- A customer cannot remove a bank account when an active payment is currently dependent on that account; the customer should be informed why removal is unavailable.

---

## 2. Payment Flex

### Purpose
Payment Flex is a short-term payment-assistance option that provides eligible customers with a limited set of payment options based on their account circumstances.

### Core functionality
- The product checks whether the customer is eligible for Payment Flex.
- Eligible customers are shown available offer details.
- Customers may choose from payment dates made available by the product.
- Customers review and accept the arrangement before it becomes active.
- A confirmation is displayed after successful acceptance and scheduling.

### Eligibility and offer presentation
- Payment Flex is not available to every customer.
- Offer Eligibility API determines whether a customer currently qualifies.
- When the customer is not eligible, Payment Flex should not be displayed as an available offer.
- The absence of an offer for an ineligible customer is expected product behavior and is not, by itself, a technical error.

### Payment-date behavior
- Eligible payment dates are determined by product and account rules.
- Not every calendar date must be selectable.
- When a customer selects an unavailable date, the product should prevent the selection and allow the customer to choose another available date.
- The current experience may not always explain why an individual date is unavailable. This is a known customer-experience limitation and does not necessarily indicate a technical defect.

### Expected behavior
- If Offer Eligibility API returns a valid not-eligible result, no offer is displayed.
- If an eligible customer selects an available date, Payment Scheduling API should create the schedule.
- If the selected date is unavailable, the customer should remain in the flow and be able to choose another date.

---

## 3. Balance Assist Plan

### Purpose
Balance Assist Plan is a structured payment-assistance option that allows eligible customers to establish a series of scheduled payments over time.

### Core functionality
- The product determines customer eligibility.
- Eligible customers may review available plan terms.
- The customer selects a plan and reviews the proposed payment schedule.
- Payment Scheduling API creates the scheduled-payment arrangement.
- Customers may later view their existing plan and upcoming scheduled payments.

### Eligibility and account status
- Offer Eligibility API determines whether the customer qualifies for an available plan.
- Account Status API provides account information used to support plan presentation and management.
- Eligibility and available plan terms may vary by account status.

### Payment scheduling
- A plan is not active until the payment schedule is successfully created.
- If Payment Scheduling API fails while the customer is setting up the plan, the experience should display an error and must not represent the plan as successfully created.
- A temporary service failure may allow a later retry to succeed.
- A failed scheduling attempt does not necessarily mean the customer is ineligible for Balance Assist Plan.

### Expected behavior
- Customers who successfully create a plan receive confirmation.
- Customers whose scheduling request fails should be able to retry when the service is available.
- Existing-plan information should reflect the successfully created schedule.

---

## Product Knowledge Authority
When another product document conflicts with this Source of Truth on product behavior or business rules, the conflict must be reviewed. This document should be treated as authoritative unless a newer approved Source of Truth is explicitly identified.
