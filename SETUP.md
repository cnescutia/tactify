# Tactify — Monetization Setup Guide

This guide walks you through setting up Supabase (user database) and Stripe (payments)
so the Tactify paywall works when deployed to HuggingFace Spaces.

---

## 1. Supabase — User Database

### Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and sign up / log in.
2. Click **New project**, choose a name (e.g. `tactify`), set a database password, pick a region close to your users.
3. Wait for the project to finish provisioning (~2 minutes).

### Run the SQL to create the users table

In your Supabase project, go to **SQL Editor** and run the following:

```sql
create table users (
  id uuid default gen_random_uuid() primary key,
  email text unique not null,
  analyses_used integer default 0,
  is_pro boolean default false,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz default now(),
  pro_since timestamptz
);
create index on users(email);
```

### Get your API credentials

1. Go to **Project Settings** > **API**.
2. Copy:
   - **Project URL** — looks like `https://xxxxxxxxxxxx.supabase.co`
   - **anon / public key** — the long JWT string under "Project API keys"

---

## 2. Stripe — Payments

### Create a Stripe account

1. Go to [stripe.com](https://stripe.com) and sign up.
2. Complete account verification (required to accept real payments).

### Create Products and Prices

Go to **Products** in the Stripe dashboard and create two products:

| Product | Price | Billing | Notes |
|---------|-------|---------|-------|
| Tactify Pro | £9.99 | Monthly recurring | Copy the Price ID (starts with `price_`) |
| Tactify Club | £49.00 | Monthly recurring | Copy the Price ID (starts with `price_`) |

### Get your API keys

Go to **Developers** > **API keys**:
- Copy the **Secret key** (starts with `sk_live_` for production, `sk_test_` for testing)
- Keep this secret — never commit it to git

---

## 3. Environment Variables for HuggingFace Spaces

In your HuggingFace Space, go to **Settings** > **Repository secrets** and add the following:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SUPABASE_URL` | `https://xxxxxxxxxxxx.supabase.co` | Your Supabase project URL |
| `SUPABASE_KEY` | `eyJ...` | Supabase anon/public key |
| `STRIPE_SECRET_KEY` | `sk_live_...` or `sk_test_...` | Stripe secret key |
| `STRIPE_PRO_PRICE_ID` | `price_...` | Stripe Price ID for Pro plan (£9.99/mo) |
| `STRIPE_CLUB_PRICE_ID` | `price_...` | Stripe Price ID for Club plan (£49/mo) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic API key for Claude |

> **Note:** All other existing secrets (ANTHROPIC_API_KEY, etc.) must remain set as before.

---

## 4. Stripe Webhook (Optional)

Tactify verifies payments by checking the Stripe session ID in the redirect URL
(`?session_id=...`) when the user returns from Stripe Checkout. This works without
a webhook endpoint.

If you want real-time subscription management (e.g. cancellations, failed payments),
you can optionally set up a webhook:

1. In Stripe Dashboard, go to **Developers** > **Webhooks** > **Add endpoint**.
2. Set the endpoint URL to your Space URL:
   `https://your-username-tactify.hf.space/stripe/webhook`
3. Select events: `checkout.session.completed`, `customer.subscription.deleted`,
   `customer.subscription.updated`.
4. Copy the **Webhook signing secret** and add it as a HuggingFace secret: `STRIPE_WEBHOOK_SECRET`.

> **Note:** The webhook endpoint is not currently implemented in Tactify (not required for the
> redirect-based payment flow). This step is only needed if you add server-side webhook handling later.

---

## 5. Testing the Integration

1. Use Stripe test mode keys (`sk_test_...`) and test price IDs during development.
2. Use Stripe's test card: `4242 4242 4242 4242`, any future expiry, any CVC.
3. After a test payment, you should be redirected back to the app with `?session_id=...`
   in the URL, and the user should be marked as Pro in Supabase.
4. Check the `users` table in Supabase to verify `is_pro = true` was set correctly.

---

## 6. Going Live

1. Switch `STRIPE_SECRET_KEY` from `sk_test_...` to `sk_live_...`.
2. Update `STRIPE_PRO_PRICE_ID` and `STRIPE_CLUB_PRICE_ID` to your live price IDs.
3. Make sure the Supabase project is on a plan that supports the expected traffic
   (Free tier supports 50,000 monthly active users).
