from fastapi import Depends

from auth.services.payment import PaymentService


def get_payment_service() -> PaymentService:
    """Get a payment service instance."""
    return PaymentService()
