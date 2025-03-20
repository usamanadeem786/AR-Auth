from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.exceptions import HTTPException
from pydantic import UUID4

from auth.apps.dashboard.dependencies import (
    BaseContext,
    DatatableColumn,
    DatatableQueryParameters,
    DatatableQueryParametersGetter,
    get_base_context,
)
from auth.apps.dashboard.forms.subscription import (
    OrganizationSubscriptionForm,
    SubscriptionCreateForm,
    SubscriptionTierForm,
    SubscriptionUpdateForm,
)
from auth.apps.dashboard.responses import HXRedirectResponse
from auth.dependencies.admin_authentication import is_authenticated_admin_session
from auth.dependencies.pagination import PaginatedObjects
from auth.dependencies.payment import get_payment_service
from auth.dependencies.repositories import get_repository
from auth.dependencies.subscription import (
    get_paginated_subscriptions,
    get_subscription_by_id_or_404,
)
from auth.dependencies.tenant import get_tenants
from auth.forms import FormHelper
from auth.models import Tenant
from auth.models.subscription import (
    Subscription,
    SubscriptionInterval,
    SubscriptionTier,
    SubscriptionTierMode,
    SubscriptionTierType,
)
from auth.repositories.role import RoleRepository
from auth.repositories.subscription import (
    SubscriptionRepository,
    SubscriptionTierRepository,
)
from auth.repositories.tenant import TenantRepository
from auth.services.payment import PaymentService
from auth.templates import templates

router = APIRouter(dependencies=[Depends(is_authenticated_admin_session)])


async def get_columns() -> list[DatatableColumn]:
    return [
        DatatableColumn("Name", "name", "name_column", ordering="name"),
        DatatableColumn(
            "Public",
            "is_public",
            "is_public_column",
            ordering="is_public",
        ),
        DatatableColumn(
            "Accounts",
            "accounts",
            "accounts_column",
            ordering="accounts",
        ),
        DatatableColumn("Tiers", "tiers", "tiers_column"),
        DatatableColumn("Tenant", "tenant", "tenant_column", ordering="tenant.name"),
    ]


async def get_list_template(hx_combobox: bool = Header(False)) -> str:
    if hx_combobox:
        return "admin/subscriptions/list_combobox.html"
    return "admin/subscriptions/list.html"


async def get_list_context(
    columns: list[DatatableColumn] = Depends(get_columns),
    datatable_query_parameters: DatatableQueryParameters = Depends(
        DatatableQueryParametersGetter(
            [
                "name",
                "is_public",
                "accounts",
                "tenant",
            ],
            ["tenant", "query"],
        )
    ),
    paginated_subscriptions: PaginatedObjects[Subscription] = Depends(
        get_paginated_subscriptions
    ),
    tenants: list[Tenant] = Depends(get_tenants),
):
    subscriptions, count = paginated_subscriptions
    return {
        "subscriptions": subscriptions,
        "count": count,
        "columns": columns,
        "datatable_query_parameters": datatable_query_parameters,
        "tenants": tenants,
    }


@router.get("/", name="dashboard.subscriptions:list")
async def list_subscriptions(
    request: Request,
    template: str = Depends(get_list_template),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    return templates.TemplateResponse(
        request,
        template,
        {**context, **list_context},
    )


@router.get("/{id:uuid}", name="dashboard.subscriptions:get")
async def get_subscription(
    request: Request,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    return templates.TemplateResponse(
        request,
        "admin/subscriptions/get/general.html",
        {
            **context,
            **list_context,
            "subscription": subscription,
            "tab": "general",
        },
    )


@router.api_route(
    "/create", methods=["GET", "POST"], name="dashboard.subscriptions:create"
)
async def create_subscription(
    request: Request,
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
    tenant_repository: TenantRepository = Depends(get_repository(TenantRepository)),
    role_repository: RoleRepository = Depends(get_repository(RoleRepository)),
    payment_service: PaymentService = Depends(get_payment_service),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    form_helper = FormHelper(
        SubscriptionCreateForm,
        "admin/subscriptions/create.html",
        request=request,
        context={**context, **list_context},
    )

    if await form_helper.is_submitted_and_valid():
        form = await form_helper.get_form()

        # Check if Stripe product ID exists
        stripe_product_id = form.stripe_product_id.data
        # Verify the product exists in Stripe
        stripe_product = await payment_service.get_product_from_stripe(
            stripe_product_id
        )

        if not stripe_product:
            form.stripe_product_id.errors.append(
                "Product not found in payment provider."
            )
            return await form_helper.get_error_response(
                "Product not found in payment provider.",
                "product_not_found",
            )

        subscription = Subscription()

        # Get roles
        roles = []
        for role_id in form.roles.data:
            role = await role_repository.get_by_id(role_id)
            if role is None:
                form.roles.errors.append("Unknown role.")
                return await form_helper.get_error_response(
                    "Unknown role.", "unknown_role"
                )
            roles.append(role)
        form.roles.data = roles

        tenant = await tenant_repository.get_by_id(form.tenant.data)
        if tenant is None:
            form.tenant.errors.append("Unknown tenant.")
            return await form_helper.get_error_response(
                "Unknown tenant.", "unknown_tenant"
            )
        form.tenant.data = tenant

        form.populate_obj(subscription)
        subscription = await repository.create(subscription)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:get", id=subscription.id),
            status_code=status.HTTP_201_CREATED,
            headers={"X-Auth-Object-Id": str(subscription.id)},
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/edit",
    methods=["GET", "POST"],
    name="dashboard.subscriptions:update",
)
async def update_subscription(
    request: Request,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
    role_repository: RoleRepository = Depends(get_repository(RoleRepository)),
    payment_service: PaymentService = Depends(get_payment_service),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):

    form_helper = FormHelper(
        SubscriptionUpdateForm,
        "admin/subscriptions/edit.html",
        object=subscription,
        request=request,
        context={**context, **list_context, "subscription": subscription},
    )

    form = await form_helper.get_form()
    form.roles.choices = [(role.id, role.display_name) for role in subscription.roles]

    if await form_helper.is_submitted_and_valid():
        # Check if Stripe product ID exists if changed
        stripe_product_id = form.stripe_product_id.data
        product_id_changed = stripe_product_id != subscription.stripe_product_id

        if product_id_changed:
            # Verify the product exists in Stripe
            stripe_product = await payment_service.get_product_from_stripe(
                stripe_product_id
            )

            if not stripe_product:
                form.stripe_product_id.errors.append(
                    "Product not found in payment provider."
                )
                return await form_helper.get_error_response(
                    "Product not found in payment provider.",
                    "product_not_found",
                )

        # Get roles
        subscription.roles = []
        for role_id in form.roles.data:
            role = await role_repository.get_by_id(role_id)
            if role is None:
                form.roles.errors.append("Unknown role.")
                return await form_helper.get_error_response(
                    "Unknown role.", "unknown_role"
                )
            subscription.roles.append(role)

        # Remove roles from form data before populating object
        del form.roles

        form.populate_obj(subscription)
        await repository.update(subscription)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:get", id=subscription.id)
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/delete",
    methods=["GET", "DELETE"],
    name="dashboard.subscriptions:delete",
)
async def delete_subscription(
    request: Request,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
    # organization_subscription_repository: OrganizationSubscriptionRepository
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    if request.method == "DELETE":
        await repository.delete(subscription)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:list"),
            status_code=status.HTTP_204_NO_CONTENT,
        )
    else:
        # Count active organization subscriptions
        active_subscriptions_count = (
            0  # In a real implementation, this would be counted
        )

        return templates.TemplateResponse(
            request,
            "admin/subscriptions/delete.html",
            {
                **context,
                **list_context,
                "subscription": subscription,
                "active_subscriptions_count": active_subscriptions_count,
            },
        )


@router.get("/{id:uuid}/tiers", name="dashboard.subscriptions:tiers")
async def list_subscription_tiers(
    request: Request,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    tiers = await tier_repository.get_by_subscription(subscription.id)
    return templates.TemplateResponse(
        request,
        "admin/subscriptions/get/tiers.html",
        {
            **context,
            **list_context,
            "subscription": subscription,
            "tiers": tiers,
            "tab": "tiers",
        },
    )


@router.api_route(
    "/{id:uuid}/tiers/create",
    methods=["GET", "POST"],
    name="dashboard.subscriptions:create_tier",
)
async def create_subscription_tier(
    request: Request,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    form_helper = FormHelper(
        SubscriptionTierForm,
        "admin/subscriptions/tiers/create.html",
        request=request,
        context={**context, **list_context, "subscription": subscription},
    )

    if await form_helper.is_submitted_and_valid():
        form = await form_helper.get_form()

        tier = SubscriptionTier()
        tier.subscription_id = subscription.id

        # Validate fields based on mode
        mode = form.mode.data
        if mode == SubscriptionTierMode.RECURRING:
            if not form.interval_count.data or not form.interval.data:
                form.interval_count.errors.append(
                    "Interval count is required for recurring tiers."
                )
                form.interval.errors.append(
                    "Interval unit is required for recurring tiers."
                )
                return await form_helper.get_error_response(
                    "Interval fields are required for recurring tiers.",
                    "invalid_fields",
                )
        elif mode == SubscriptionTierMode.ONE_TIME:
            form.type.data = None
            form.interval.data = None
            form.interval_count.data = None

        stripe_price_id = form.stripe_price_id.data
        stripe_price = await payment_service.get_price_from_stripe(stripe_price_id)

        if not stripe_price:
            form.stripe_price_id.errors.append("Price not found in payment provider.")
            return await form_helper.get_error_response(
                "Price not found in payment provider.", "price_not_found"
            )
        elif stripe_price.product != subscription.stripe_product_id:
            form.stripe_price_id.errors.append("Price not found for this subscription.")
            return await form_helper.get_error_response(
                "Price not found for this subscription.", "price_not_found"
            )

        form.populate_obj(tier)
        tier = await tier_repository.create(tier)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:tiers", id=subscription.id)
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/tiers/{tier_id:uuid}/edit",
    methods=["GET", "POST"],
    name="dashboard.subscriptions:edit_tier",
)
async def edit_subscription_tier(
    request: Request,
    tier_id: UUID4,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    # Get the tier
    tier = await tier_repository.get_by_id(tier_id)
    if not tier or tier.subscription_id != subscription.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tier with id {tier_id} not found for this subscription",
        )

    form_helper = FormHelper(
        SubscriptionTierForm,
        "admin/subscriptions/tiers/edit.html",
        object=tier,
        request=request,
        context={
            **context,
            **list_context,
            "subscription": subscription,
            "tier": tier,
        },
    )

    if await form_helper.is_submitted_and_valid():
        form = await form_helper.get_form()

        # Validate fields based on mode
        mode = form.mode.data
        if mode == SubscriptionTierMode.RECURRING:
            if not form.interval_count.data or not form.interval.data:
                form.interval_count.errors.append(
                    "Interval count is required for recurring tiers."
                )
                form.interval.errors.append(
                    "Interval unit is required for recurring tiers."
                )
                return await form_helper.get_error_response(
                    "Interval fields are required for recurring tiers.",
                    "invalid_fields",
                )
        elif mode == SubscriptionTierMode.ONE_TIME:
            form.type.data = None
            form.interval.data = None
            form.interval_count.data = None

        stripe_price_id = form.stripe_price_id.data

        if stripe_price_id != tier.stripe_price_id:
            stripe_price = await payment_service.get_price_from_stripe(stripe_price_id)
            if not stripe_price:
                form.stripe_price_id.errors.append(
                    "Price not found in payment provider."
                )
                return await form_helper.get_error_response(
                    "Price not found in payment provider.", "price_not_found"
                )
            elif stripe_price.product != subscription.stripe_product_id:
                form.stripe_price_id.errors.append(
                    "Price not found for this subscription."
                )
                return await form_helper.get_error_response(
                    "Price not found for this subscription.", "price_not_found"
                )
        print(form.data)
        form.populate_obj(tier)
        await tier_repository.update(tier)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:tiers", id=subscription.id)
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/tiers/{tier_id:uuid}/delete",
    methods=["GET", "DELETE"],
    name="dashboard.subscriptions:delete_tier",
)
async def delete_subscription_tier(
    request: Request,
    tier_id: UUID4,
    subscription: Subscription = Depends(get_subscription_by_id_or_404),
    tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    # Get the tier
    tier = await tier_repository.get_by_id(tier_id)
    if not tier or tier.subscription_id != subscription.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tier with id {tier_id} not found for this subscription",
        )

    if request.method == "DELETE":
        await tier_repository.delete(tier)

        return HXRedirectResponse(
            request.url_for("dashboard.subscriptions:tiers", id=subscription.id),
            status_code=status.HTTP_204_NO_CONTENT,
        )
    else:
        # Count active organization subscriptions using this tier
        active_subscriptions_count = (
            0  # In a real implementation, this would be counted
        )

        return templates.TemplateResponse(
            request,
            "admin/subscriptions/tiers/delete.html",
            {
                **context,
                **list_context,
                "subscription": subscription,
                "tier": tier,
                "active_subscriptions_count": active_subscriptions_count,
            },
        )


@router.get("/tiers", name="dashboard.subscription_tiers:list")
async def list_subscription_tiers_combobox(
    request: Request,
    query: str = None,
    tier_repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
    context: BaseContext = Depends(get_base_context),
    hx_combobox: bool = Header(False),
):
    # Get all tiers
    tiers = await tier_repository.get_all_with_subscription()

    # Filter by query if provided
    if query:
        tiers = [
            tier
            for tier in tiers
            if query.lower() in tier.name.lower()
            or (tier.subscription and query.lower() in tier.subscription.name.lower())
        ]

    if hx_combobox:
        return templates.TemplateResponse(
            request,
            "admin/subscriptions/tiers/list_combobox.html",
            {
                **context,
                "tiers": tiers,
            },
        )

    # For now, just return the combobox view
    return templates.TemplateResponse(
        request,
        "admin/subscriptions/tiers/list_combobox.html",
        {
            **context,
            "tiers": tiers,
        },
    )
