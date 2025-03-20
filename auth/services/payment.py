from typing import Any, Optional

import stripe
from pydantic import UUID4

from auth.models.organization import Organization
from auth.models.user import User
from auth.settings import settings


class PaymentService:
    def __init__(self):
        if not settings.stripe_secret_key:
            raise ValueError("Payment provider secret key is not configured")

        stripe.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret

    async def create_organization_customer(self, organization: Organization) -> str:
        """Create a payment customer for an organization and return the customer ID."""

        # Find an owner or admin to use as the email contact
        email = None
        for member in organization.members:
            if member.is_owner:
                email = member.user.email
                break

        customer = stripe.Customer.create(
            name=organization.name,
            email=email,
        )

        return customer.id

    async def create_organization_customer_portal_session(
        self,
        user: User,
        return_url: str,
    ) -> str:
        """Create a Customer Portal session for an organization and return the URL."""
        # Validate that the user has a Stripe customer ID
        if not user.stripe_customer_id:
            raise ValueError("User has no associated payment customer")

        # Create the portal session with appropriate configuration
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    async def create_organization_checkout_session(
        self,
        user: User,
        organization: Organization,
        price_id: str,
        success_url: str,
        cancel_url: str,
        quantity: int = 1,
        mode: str = "subscription",
    ) -> str:
        """Create a checkout session for an organization subscription and return the URL."""
        if not user.stripe_customer_id:
            raise ValueError("User has no associated payment customer")

        session_params = {
            "customer": user.stripe_customer_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "mode": mode,
            "client_reference_id": str(organization.id),
            "metadata": {
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        }

        session_params["line_items"] = [
            {
                "price": price_id,
                "quantity": quantity,
            }
        ]

        session = await stripe.checkout.Session.create_async(**session_params)
        return session.url

    async def get_product_from_stripe(self, product_id: str) -> dict[str, Any]:
        """Get a product from Stripe by ID."""
        try:
            product = await stripe.Product.retrieve_async(product_id)
            return product
        except stripe.error.StripeError:
            return None

    async def get_prices_for_product(self, product_id: str) -> list[dict[str, Any]]:
        """Get all prices for a product from Stripe."""
        try:
            prices = await stripe.Price.list_async(product=product_id)
            return prices
        except stripe.error.StripeError:
            return []

    async def get_price_from_stripe(self, price_id: str) -> dict[str, Any]:
        """Get a price from Stripe by ID."""
        try:
            price = await stripe.Price.retrieve_async(price_id)
            return price
        except stripe.error.StripeError:
            return None

    async def get_subscription_from_stripe(
        self, subscription_id: str
    ) -> dict[str, Any]:
        """Get a subscription from Stripe."""
        try:
            subscription = await stripe.Subscription.retrieve_async(subscription_id)
            return subscription
        except stripe.error.StripeError:
            return None

    async def get_line_items(self, session_id: str) -> dict[str, Any]:
        """Get line items for a checkout session."""
        session = await stripe.checkout.Session.list_line_items_async(session_id)
        return session

    async def handle_subscription_updated(
        self, event_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle subscription.updated event from payment provider."""
        subscription = event_data["object"]

        return {
            "subscription_id": subscription["id"],
            "customer_id": subscription["customer"],
            "status": subscription["status"],
            "current_period_end": subscription.get("current_period_end"),
            "items": subscription.get("items", {}).get("data", []),
            "quantity": subscription.get(
                "quantity", 1
            ),  # Add quantity for credit-based plans
            "metadata": subscription.get("metadata", {}),
        }

    async def handle_subscription_deleted(self, event_data: dict[str, Any]) -> None:
        """Handle subscription.deleted event from payment provider."""
        subscription = event_data["object"]
        subscription_id = subscription["id"]
        customer_id = subscription["customer"]

        # Return data that can be used by the webhook handler
        return {"subscription_id": subscription_id, "customer_id": customer_id}

    async def handle_payment_failed(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """Handle invoice.payment_failed event from payment provider."""
        invoice = event_data["object"]

        return {
            "invoice_id": invoice["id"],
            "customer_id": invoice["customer"],
            "subscription_id": invoice.get("subscription"),
            "next_payment_attempt": invoice.get("next_payment_attempt"),
            "hosted_invoice_url": invoice.get("hosted_invoice_url"),
        }

    def construct_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        """Construct a payment provider event from webhook payload and signature."""
        if not self.webhook_secret:
            raise ValueError("Payment provider webhook secret is not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=sig_header, secret=self.webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise ValueError(f"Invalid signature: {str(e)}")
        except Exception as e:
            # Other errors
            raise ValueError(f"Error constructing event: {str(e)}")
