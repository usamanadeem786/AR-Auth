import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import UUID4, BaseModel

from auth.dependencies.organizations import get_organization_by_id_or_404
from auth.dependencies.payment import get_payment_service
from auth.dependencies.repositories import get_repository
from auth.dependencies.users import current_active_user
from auth.models.organization import Organization
from auth.models.organization_subscription import (
    OrganizationSubscription,
    SubscriptionStatus,
)
from auth.models.subscription import (
    Subscription,
    SubscriptionEvent,
    SubscriptionEventStatus,
    SubscriptionInterval,
    SubscriptionTier,
    SubscriptionTierMode,
    SubscriptionTierType,
)
from auth.models.user import User
from auth.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from auth.repositories.organization_subscription import (
    OrganizationSubscriptionRepository,
)
from auth.repositories.subscription import (
    SubscriptionEventRepository,
    SubscriptionTierRepository,
)
from auth.repositories.user import UserRepository
from auth.services.payment import PaymentService
from auth.settings import settings

router = APIRouter(prefix="/billing", tags=["billing"])
router_webhook = APIRouter(prefix="/billing", tags=["webhook"])


class CustomerPortalRequest(BaseModel):
    return_url: str = "http://localhost:8000/account"


class CustomerPortalResponse(BaseModel):
    url: str


class CheckoutSessionRequest(BaseModel):
    price_id: UUID4
    success_url: str = "http://localhost:8000/success?session_id={CHECKOUT_SESSION_ID}"
    cancel_url: str = "http://localhost:8000/cancel"


class CheckoutSessionResponse(BaseModel):
    url: str


@router.post(
    "/organizations/{id:uuid}/portal",
    response_model=CustomerPortalResponse,
    status_code=status.HTTP_200_OK,
)
async def create_organization_customer_portal_session(
    customer_portal: CustomerPortalRequest,
    user: User = Depends(current_active_user),
    organization: Organization = Depends(get_organization_by_id_or_404),
    payment_service: PaymentService = Depends(get_payment_service),
    organization_member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
):
    """Create a Customer Portal session for an organization."""
    try:
        # Check if the user is the owner of the organization
        org_member = await organization_member_repository.get_by_user_and_org(
            user.id, organization.id
        )

        if not org_member.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the organization owner can access the customer portal",
            )

        # Check if the organization has any subscriptions
        subscriptions = (
            await organization_subscription_repository.get_all_by_organization(
                organization.id
            )
        )

        if not subscriptions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must have at least one subscription to access the customer portal",
            )

        # Create a customer portal session
        portal_url = await payment_service.create_organization_customer_portal_session(
            user, customer_portal.return_url
        )

        return CustomerPortalResponse(url=portal_url)

    except HTTPException:
        # Re-raise HTTP exceptions as they already have appropriate status codes
        raise
    except stripe.error.InvalidRequestError as e:
        # Handle Stripe-specific errors for invalid requests
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request to payment provider: {str(e)}",
        )
    except stripe.error.AuthenticationError:
        # Handle authentication errors with Stripe
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error with payment provider",
        )
    except stripe.error.APIConnectionError:
        # Handle connection errors with Stripe API
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to payment provider",
        )
    except stripe.error.StripeError as e:
        # Handle any other Stripe-specific errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment provider error: {str(e)}",
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/organizations/{id:uuid}/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_organization_checkout_session(
    checkout: CheckoutSessionRequest,
    organization: Organization = Depends(get_organization_by_id_or_404),
    user: User = Depends(current_active_user),
    payment_service: PaymentService = Depends(get_payment_service),
    user_repository: UserRepository = Depends(get_repository(UserRepository)),
    subscription_tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
):
    """Create a checkout session for an organization subscription."""
    try:
        # Get the subscription tier
        subscription_tier = (
            await subscription_tier_repository.get_with_subscription_by_id(
                checkout.price_id
            )
        )
        if not subscription_tier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription tier with id {checkout.price_id} not found",
            )

        # Check if the organization already has this subscription
        existing_subscription = (
            await organization_subscription_repository.get_by_organization_and_tier(
                organization.id, subscription_tier.id
            )
        )

        # If subscription already exists and it's not a one-time payment, prevent duplicate
        if (
            existing_subscription
            and subscription_tier.mode != SubscriptionTierMode.ONE_TIME
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization already has a subscription with this tier",
            )

        # If not a primary subscription, check if the organization has at least one active primary subscription
        if subscription_tier.type != SubscriptionTierType.PRIMARY:
            # Get active primary subscriptions
            active_subscriptions = (
                await organization_subscription_repository.get_active_by_organization(
                    organization.id
                )
            )

            has_primary = any(
                sub.tier.type == SubscriptionTierType.PRIMARY
                for sub in active_subscriptions
            )

            if not has_primary:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization must have an active primary subscription before purchasing this tier",
                )

        # Create a payment customer if one doesn't exist
        if not user.stripe_customer_id:
            user.stripe_customer_id = (
                await payment_service.create_organization_customer(organization)
            )
            await user_repository.update(user)

        # Create a checkout session with appropriate parameters based on price type
        checkout_url = await payment_service.create_organization_checkout_session(
            user,
            organization,
            subscription_tier.stripe_price_id,
            checkout.success_url,
            checkout.cancel_url,
            quantity=subscription_tier.quantity,
            mode=(
                "subscription"
                if subscription_tier.mode == SubscriptionTierMode.RECURRING
                else "payment"
            ),
        )

        return CheckoutSessionResponse(url=checkout_url)

    except HTTPException:
        # Re-raise HTTP exceptions as they already have appropriate status codes
        raise
    except stripe.error.InvalidRequestError as e:
        # Handle invalid requests to Stripe API
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request to payment provider: {str(e)}",
        )
    except stripe.error.AuthenticationError:
        # Handle API key issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error with payment provider",
        )
    except stripe.error.APIConnectionError:
        # Handle network issues when connecting to Stripe
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to payment provider",
        )
    except stripe.error.StripeError as e:
        # Handle all other Stripe errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment provider error: {str(e)}",
        )
    except Exception as e:
        print("Unexpected error in checkout session:", str(e))
        # Handle any other unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router_webhook.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
)
async def payment_webhook(
    request: Request,
    stripe_signature: Annotated[str, Header(alias="Stripe-Signature")],
    payment_service: PaymentService = Depends(get_payment_service),
    organization_repository: OrganizationRepository = Depends(
        get_repository(OrganizationRepository)
    ),
    subscription_tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
    stripe_event_repository: SubscriptionEventRepository = Depends(
        get_repository(SubscriptionEventRepository)
    ),
):
    """Handle payment provider webhook events."""
    # Read the request body
    payload = await request.body()

    try:
        # Verify the webhook signature
        event = payment_service.construct_event(payload, stripe_signature)
    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid webhook signature: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook signature: {str(e)}",
        )
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook request: {str(e)}",
        )

    # Process the event based on its type
    event_type = event["type"]
    event_data = event["data"]["object"]
    print(f"Processing webhook event: {event_type}")

    try:
        # New Subscription Created or One-time payment
        if event_type == "checkout.session.completed":
            await handle_checkout_session_completed(
                event_data,
                organization_repository,
                subscription_tier_repository,
                organization_subscription_repository,
                payment_service,
            )

        # Subscription created event - for first-time subscriptions
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(
                event_data,
                organization_repository,
                subscription_tier_repository,
                organization_subscription_repository,
            )

        # Subscription renewed/updated/modified
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(
                event_data,
                subscription_tier_repository,
                organization_subscription_repository,
            )

        # Subscription canceled
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(
                event_data,
                organization_subscription_repository,
            )

        # Invoice paid - subscription renewed successfully
        elif event_type == "invoice.paid":
            await handle_invoice_paid(
                event_data,
                organization_subscription_repository,
                subscription_tier_repository,
            )

        # Invoice payment failed
        elif event_type == "invoice.payment_failed":
            await handle_invoice_payment_failed(
                event_data,
                organization_subscription_repository,
            )
        else:
            print(f"Unhandled webhook event type: {event_type}")
    except Exception as e:
        # Log the error but don't return an error response to Stripe
        # Per Stripe's best practices, we should return a 200 response even if processing fails
        # to prevent Stripe from retrying the webhook
        print(f"Error processing webhook {event_type}: {str(e)}")
        await stripe_event_repository.create(
            SubscriptionEvent(
                event_id=event["id"],
                type=event_type,
                data=event_data,
                error=str(e),
                status=SubscriptionEventStatus.CRITICAL,
            )
        )
    else:
        if event_type in [
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
        ]:
            await stripe_event_repository.create(
                SubscriptionEvent(
                    event_id=event["id"],
                    type=event_type,
                    data=event_data,
                    status=SubscriptionEventStatus.NORMAL,
                )
            )

    # Return a 200 response to acknowledge receipt of the event
    # Always return 200 to Stripe, even if there's an error, to prevent retries
    return Response(status_code=status.HTTP_200_OK)


def map_stripe_to_subscription_status(stripe_status: str) -> SubscriptionStatus:
    """Map Stripe subscription status to internal status."""
    status_mapping = {
        "incomplete": SubscriptionStatus.PENDING,
        "incomplete_expired": SubscriptionStatus.EXPIRED,
        "trialing": SubscriptionStatus.TRIALING,
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.PAST_DUE,
    }
    return status_mapping.get(stripe_status, SubscriptionStatus.PENDING)


async def handle_invoice_paid(
    invoice: dict,
    organization_subscription_repository: OrganizationSubscriptionRepository,
    subscription_tier_repository: SubscriptionTierRepository,
):
    """Handle invoice.paid event - subscription renewal/payment success."""
    try:
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            raise ValueError("No subscription ID in invoice paid event")

        # Find the organization subscription
        organization_subscription = (
            await organization_subscription_repository.get_by_stripe_subscription_id(
                subscription_id
            )
        )

        if not organization_subscription:
            raise ValueError(
                f"No organization subscription found for Stripe subscription ID: {subscription_id}"
            )

        # Update the subscription status to active
        organization_subscription.status = SubscriptionStatus.ACTIVE

        # Update the expiry date based on the invoice period
        period_end = (
            invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
        )
        if period_end:
            organization_subscription.expires_at = datetime.fromtimestamp(
                period_end, tz=UTC
            )

        await organization_subscription_repository.update(organization_subscription)
        print(f"Subscription {subscription_id} renewed successfully")
    except Exception as e:
        print(f"Error handling invoice.paid event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK


async def handle_invoice_payment_failed(
    invoice: dict,
    organization_subscription_repository: OrganizationSubscriptionRepository,
):
    """Handle invoice.payment_failed event."""
    try:
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            raise ValueError("No subscription ID in invoice payment failed event")

        # Find the organization subscription
        organization_subscription = (
            await organization_subscription_repository.get_by_stripe_subscription_id(
                subscription_id
            )
        )

        if not organization_subscription:
            raise ValueError(
                f"No organization subscription found for Stripe subscription ID: {subscription_id}"
            )

        # Update the subscription status to past_due
        organization_subscription.status = SubscriptionStatus.PAST_DUE

        # The subscription hasn't been canceled yet, so we keep the expiry date
        await organization_subscription_repository.update(organization_subscription)

        # Here you would typically implement notification logic
        # e.g., send an email to the organization owner
        print(f"Subscription {subscription_id} payment failed, marked as past_due")
    except Exception as e:
        print(f"Error handling invoice.payment_failed event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK


async def handle_checkout_session_completed(
    session: dict,
    organization_repository: OrganizationRepository,
    subscription_tier_repository: SubscriptionTierRepository,
    organization_subscription_repository: OrganizationSubscriptionRepository,
    payment_service: PaymentService,
):
    """Handle checkout session completed event for both subscriptions and one-time payments."""
    try:
        subscription_id = session.get("subscription")
        payment_status = session.get("payment_status")

        # Validate payment status
        if payment_status != "paid":
            raise ValueError(f"Checkout session not paid: {session.get('id')}")

        # If this is a subscription checkout, it will be handled by the subscription.created event
        if subscription_id:
            print(
                f"Checkout for subscription {subscription_id} completed, will be handled by subscription.created event"
            )
            return

        # For one-time payments, we need to handle it here
        line_items = await payment_service.get_line_items(session.get("id"))

        if not line_items or not line_items.get("data"):
            raise ValueError(f"No line items found for session {session.get('id')}")

        price_id = line_items.get("data")[0].get("price", {}).get("id")
        if not price_id:
            raise ValueError(
                f"No price ID found in checkout session {session.get('id')}"
            )

        # Look up the subscription tier
        subscription_tier = await subscription_tier_repository.get_by_stripe_price_id(
            price_id
        )
        if not subscription_tier:
            raise ValueError(
                f"No subscription tier found for Stripe price ID: {price_id}"
            )

        # Get the organization from metadata or client reference
        organization_id = session.get("client_reference_id")
        if not organization_id:
            raise ValueError(
                f"No organization ID found in checkout session {session.get('id')}"
            )

        organization = await organization_repository.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"No organization found with ID: {organization_id}")

        # For one-time purchases, always create a new subscription object
        if subscription_tier.mode == SubscriptionTierMode.ONE_TIME:
            # Create a unique subscription ID for one-time payments
            one_time_subscription_id = f"one_time_{session.get('id')}"

            # Create organization subscription for one-time purchase
            organization_subscription = OrganizationSubscription(
                organization_id=organization.id,
                tier_id=subscription_tier.id,
                accounts=(
                    subscription_tier.subscription.accounts
                    if subscription_tier.subscription
                    else 1
                ),
                status=SubscriptionStatus.ACTIVE,
                quantity=subscription_tier.quantity,
                interval=None,  # One-time purchases don't have an interval
                interval_count=None,
                stripe_subscription_id=one_time_subscription_id,
                expires_at=None,  # One-time purchases don't expire
                grace_period=None,  # One-time purchases don't have a grace period
            )

            # If the subscription tier's parent subscription has roles, add them to the organization subscription
            if subscription_tier.subscription and subscription_tier.subscription.roles:
                organization_subscription.roles = subscription_tier.subscription.roles

            await organization_subscription_repository.create(organization_subscription)
            print(
                f"One-time purchase created for organization {organization.id}, tier {subscription_tier.id}"
            )
    except Exception as e:
        print(f"Error handling checkout.session.completed event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK


async def handle_subscription_created(
    subscription: dict,
    organization_repository: OrganizationRepository,
    subscription_tier_repository: SubscriptionTierRepository,
    organization_subscription_repository: OrganizationSubscriptionRepository,
):
    """Handle subscription created event."""
    try:
        customer_id = subscription.get("customer")
        if not customer_id:
            raise ValueError("No customer ID in subscription created event")

        subscription_status = subscription.get("status")
        subscription_id = subscription.get("id")

        if not subscription_id:
            raise ValueError("No subscription ID in subscription created event")

        # Get the price ID from the subscription
        items = subscription.get("items", {}).get("data", [])
        if not items:
            raise ValueError(f"No items in subscription {subscription_id}")

        price_id = items[0].get("price", {}).get("id")
        if not price_id:
            raise ValueError(f"No price ID in subscription {subscription_id}")

        # Look up the subscription tier by stripe_price_id
        subscription_tier = await subscription_tier_repository.get_by_stripe_price_id(
            price_id
        )

        if not subscription_tier:
            raise ValueError(
                f"No subscription tier found for Stripe price ID: {price_id}"
            )

        # Convert to internal status
        mapped_status = map_stripe_to_subscription_status(subscription_status)

        # Get current period end for expiry date
        current_period_end = subscription.get("current_period_end")
        expires_at = None

        if current_period_end:
            expires_at = datetime.fromtimestamp(current_period_end, tz=UTC)

        # Try to find an organization with this customer ID
        organization = await organization_repository.get_by_user_customer_id(
            customer_id
        )

        if not organization:
            raise ValueError(f"No organization found for customer ID: {customer_id}")

        # Check if there's an existing subscription for this organization and tier
        existing_subscription = (
            await organization_subscription_repository.get_by_organization_and_tier(
                organization.id, subscription_tier.id
            )
        )

        # For recurring subscriptions, we only create a new one if it doesn't exist
        if (
            existing_subscription
            and subscription_tier.mode == SubscriptionTierMode.RECURRING
        ):
            # Update the existing subscription instead of creating a new one
            await handle_subscription_updated(
                subscription,
                subscription_tier_repository,
                organization_subscription_repository,
            )
            return

        # Update quantity handling
        quantity = subscription.get("quantity", 1)
        if subscription_tier.quantity > 1:
            quantity = subscription_tier.quantity

        # Create organization subscription
        organization_subscription = OrganizationSubscription(
            organization_id=organization.id,
            tier_id=subscription_tier.id,
            stripe_subscription_id=subscription_id,
            accounts=(
                subscription_tier.subscription.accounts
                if subscription_tier.subscription
                else 1
            ),
            status=mapped_status,
            quantity=quantity,
            interval=subscription_tier.interval,
            interval_count=subscription_tier.interval_count,
            expires_at=expires_at,
            grace_period=7,  # Default grace period
        )

        # If the subscription_tier's parent subscription has roles, add them to the organization subscription
        if subscription_tier.subscription and subscription_tier.subscription.roles:
            organization_subscription.roles = subscription_tier.subscription.roles

        await organization_subscription_repository.create(organization_subscription)
        print(
            f"Subscription created for organization {organization.id}, tier {subscription_tier.id}"
        )
    except Exception as e:
        print(f"Error handling subscription.created event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK


async def handle_subscription_updated(
    subscription: dict,
    subscription_tier_repository: SubscriptionTierRepository,
    organization_subscription_repository: OrganizationSubscriptionRepository,
):
    """Handle subscription updated event."""
    try:
        subscription_id = subscription.get("id")
        if not subscription_id:
            raise ValueError("No subscription ID in subscription updated event")

        subscription_status = subscription.get("status")

        # Get the price ID from the subscription
        items = subscription.get("items", {}).get("data", [])
        if not items:
            raise ValueError(f"No items in subscription {subscription_id}")

        price_id = items[0].get("price", {}).get("id")
        if not price_id:
            raise ValueError(f"No price ID in subscription {subscription_id}")

        # Look up the subscription tier by stripe_price_id
        subscription_tier = await subscription_tier_repository.get_by_stripe_price_id(
            price_id
        )

        if not subscription_tier:
            raise ValueError(
                f"No subscription tier found for Stripe price ID: {price_id}"
            )

        # Convert to internal status
        mapped_status = map_stripe_to_subscription_status(subscription_status)

        # Get current period end for expiry date
        current_period_end = subscription.get("current_period_end")
        expires_at = None

        if current_period_end:
            expires_at = datetime.fromtimestamp(current_period_end, tz=UTC)

        # Try to find an organization subscription with this ID
        organization_subscription = (
            await organization_subscription_repository.get_by_stripe_subscription_id(
                subscription_id
            )
        )

        if not organization_subscription:
            raise ValueError(
                f"No organization subscription found for Stripe subscription ID: {subscription_id}"
            )

        # Update organization subscription
        organization_subscription.status = mapped_status

        # Update expiry date if available
        if expires_at:
            organization_subscription.expires_at = expires_at

        # Update quantity
        quantity = subscription.get("quantity", 1)
        if subscription_tier.quantity > 1:
            quantity = subscription_tier.quantity
        organization_subscription.quantity = quantity

        # Handle seat/account changes
        # if "items" in subscription and "data" in subscription["items"]:
        #     for item in subscription["items"]["data"]:
        #         if "quantity" in item:
        #             # This might be a seat update
        #             organization_subscription.accounts = item["quantity"]
        #             break

        # Only update other subscription details if tier has changed
        if subscription_tier.id != organization_subscription.tier_id:
            organization_subscription.tier_id = subscription_tier.id
            organization_subscription.interval = subscription_tier.interval
            organization_subscription.interval_count = subscription_tier.interval_count

            # Update accounts limit if subscription has changed
            if subscription_tier.subscription:
                organization_subscription.accounts = (
                    subscription_tier.subscription.accounts
                )

                # Update roles if subscription has changed
                if subscription_tier.subscription.roles:
                    organization_subscription.roles = (
                        subscription_tier.subscription.roles
                    )

        await organization_subscription_repository.update(organization_subscription)
        print(f"Subscription {subscription_id} updated")
    except Exception as e:
        print(f"Error handling subscription.updated event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK


async def handle_subscription_deleted(
    subscription: dict,
    organization_subscription_repository: OrganizationSubscriptionRepository,
):
    """Handle subscription deleted event."""
    try:
        subscription_id = subscription.get("id")
        if not subscription_id:
            raise ValueError("No subscription ID in subscription deleted event")

        # Try to find an organization subscription with this ID
        organization_subscription = (
            await organization_subscription_repository.get_by_stripe_subscription_id(
                subscription_id
            )
        )

        if not organization_subscription:
            raise ValueError(
                f"No organization subscription found for Stripe subscription ID: {subscription_id}"
            )

        # Cancel at period end might have different handling than immediate cancellation
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)

        if cancel_at_period_end:
            # This will be canceled at the end of the period, but still active now
            organization_subscription.status = SubscriptionStatus.ACTIVE
            # No need to change the expiry date as it will remain valid until the end of period
        else:
            # Immediate cancellation
            organization_subscription.status = SubscriptionStatus.CANCELED
            # Optionally set expires_at to now to immediately revoke access
            organization_subscription.expires_at = datetime.now(UTC)

        await organization_subscription_repository.update(organization_subscription)
        print(f"Subscription {subscription_id} marked as canceled")
    except Exception as e:
        print(f"Error handling subscription.deleted event: {str(e)}")
        # We don't re-raise to ensure webhook returns 200 OK
