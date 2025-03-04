from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from auth.apps.dashboard.dependencies import (BaseContext, DatatableColumn,
                                              DatatableQueryParameters,
                                              DatatableQueryParametersGetter,
                                              get_base_context)
from auth.apps.dashboard.forms.subscription_plan import (
    SubscriptionPlanCreateForm, SubscriptionPlanUpdateForm)
from auth.apps.dashboard.responses import HXRedirectResponse
from auth.dependencies.admin_authentication import \
    is_authenticated_admin_session
from auth.dependencies.pagination import PaginatedObjects
from auth.dependencies.repositories import get_repository
from auth.dependencies.subscription_plan import (
    get_paginated_subscription_plans, get_subscription_plan_by_id_or_404)
from auth.forms import FormHelper
from auth.models.subscription_plan import SubscriptionPlan
from auth.models.user_subscription import UserSubscription
from auth.repositories.role import RoleRepository
from auth.repositories.subscription_plan import SubscriptionPlanRepository
from auth.repositories.tenant import TenantRepository
from auth.repositories.user_subscription import UserSubscriptionRepository
from auth.templates import templates

router = APIRouter(dependencies=[Depends(is_authenticated_admin_session)])


async def get_columns() -> list[DatatableColumn]:
    return [
        DatatableColumn("Name", "name", "name_column", ordering="name"),
        DatatableColumn(
            "Granted by default",
            "granted_by_default",
            "granted_by_default_column",
            ordering="granted_by_default",
        ),
        DatatableColumn(
            "Expiry interval",
            "expiry_interval",
            "expiry_interval_column",
            ordering="expiry_interval",
        ),
        DatatableColumn(
            "Expiry unit",
            "expiry_unit",
            "expiry_unit_column",
            ordering="expiry_unit",
        ),
    ]


async def get_list_context(
    columns: list[DatatableColumn] = Depends(get_columns),
    datatable_query_parameters: DatatableQueryParameters = Depends(
        DatatableQueryParametersGetter(
            ["name", "granted_by_default", "expiry_interval", "expiry_unit"]
        )
    ),
    paginated_plans: PaginatedObjects[SubscriptionPlan] = Depends(
        get_paginated_subscription_plans
    ),
):
    subscription_plans, count = paginated_plans
    return {
        "subscription_plans": subscription_plans,
        "count": count,
        "columns": columns,
        "datatable_query_parameters": datatable_query_parameters,
    }


async def get_list_template(hx_combobox: bool = Header(False)) -> str:
    if hx_combobox:
        return "admin/subscription_plans/list_combobox.html"
    return "admin/subscription_plans/list.html"


@router.get("/", name="dashboard.subscription_plans:list")
async def list_subscription_plans(
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


@router.get("/{id:uuid}", name="dashboard.subscription_plans:get")
async def get_subscription_plan(
    request: Request,
    subscription_plan: SubscriptionPlan = Depends(get_subscription_plan_by_id_or_404),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    return templates.TemplateResponse(
        request,
        "admin/subscription_plans/get/general.html",
        {
            **context,
            **list_context,
            "subscription_plan": subscription_plan,
            "tab": "general",
        },
    )


@router.api_route(
    "/create", methods=["GET", "POST"], name="dashboard.subscription_plans:create"
)
async def create_subscription_plan(
    request: Request,
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
    tenant_repository: TenantRepository = Depends(TenantRepository),
    role_repository: RoleRepository = Depends(get_repository(RoleRepository)),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    form_helper = FormHelper(
        SubscriptionPlanCreateForm,
        "admin/subscription_plans/create.html",
        request=request,
        context={**context, **list_context},
    )

    if await form_helper.is_submitted_and_valid():
        form = await form_helper.get_form()
        subscription_plan = SubscriptionPlan()

        # Get roles
        roles = []
        for role_id in form.data["roles"]:
            role = await role_repository.get_by_id(role_id)
            if role is None:
                form.roles.errors.append("Unknown role.")
                return await form_helper.get_error_response(
                    "Unknown role.", "unknown_role"
                )
            roles.append(role)
        form.roles.data = roles

        tenant = await tenant_repository.get_by_id(form.data["tenant"])
        if tenant is None:
            form.tenant.errors.append("Unknown tenant.")
            return await form_helper.get_error_response(
                "Unknown tenant.", "unknown_tenant"
            )
        form.tenant.data = tenant

        form.populate_obj(subscription_plan)
        subscription_plan = await repository.create(subscription_plan)

        return HXRedirectResponse(
            request.url_for(
                "dashboard.subscription_plans:get", id=subscription_plan.id
            ),
            status_code=status.HTTP_201_CREATED,
            headers={"X-Auth-Object-Id": str(subscription_plan.id)},
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/edit",
    methods=["GET", "POST"],
    name="dashboard.subscription_plans:update",
)
async def update_subscription_plan(
    request: Request,
    subscription_plan: SubscriptionPlan = Depends(get_subscription_plan_by_id_or_404),
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
    role_repository: RoleRepository = Depends(get_repository(RoleRepository)),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    form_helper = FormHelper(
        SubscriptionPlanUpdateForm,
        "admin/subscription_plans/edit.html",
        object=subscription_plan,
        request=request,
        context={**context, **list_context, "subscription_plan": subscription_plan},
    )

    form = await form_helper.get_form()
    form.roles.choices = [
        (role.id, role.display_name) for role in subscription_plan.roles
    ]

    if await form_helper.is_submitted_and_valid():

        # Get roles
        subscription_plan.roles = []
        for role_id in form.data["roles"]:
            role = await role_repository.get_by_id(role_id)
            if role is None:
                form.roles.errors.append("Unknown role.")
                return await form_helper.get_error_response(
                    "Unknown role.", "unknown_role"
                )
            subscription_plan.roles.append(role)

        del form.roles
        form.populate_obj(subscription_plan)
        await repository.update(subscription_plan)

        return HXRedirectResponse(
            request.url_for("dashboard.subscription_plans:get", id=subscription_plan.id)
        )

    return await form_helper.get_response()


@router.api_route(
    "/{id:uuid}/delete",
    methods=["GET", "DELETE"],
    name="dashboard.subscription_plans:delete",
)
async def delete_subscription_plan(
    request: Request,
    subscription_plan: SubscriptionPlan = Depends(get_subscription_plan_by_id_or_404),
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
    user_subscription_repository: UserSubscriptionRepository = Depends(
        get_repository(UserSubscriptionRepository)
    ),
    list_context=Depends(get_list_context),
    context: BaseContext = Depends(get_base_context),
):
    if request.method == "DELETE":
        await repository.delete(subscription_plan)

        return HXRedirectResponse(
            request.url_for("dashboard.subscription_plans:list"),
            status_code=status.HTTP_204_NO_CONTENT,
        )
    else:

        # Count user subscriptions
        statement = select(UserSubscription).where(
            UserSubscription.subscription_plan_id == subscription_plan.id
        )
        user_subscriptions_count = await user_subscription_repository._count(statement)

        return templates.TemplateResponse(
            request,
            "admin/subscription_plans/delete.html",
            {
                **context,
                **list_context,
                "subscription_plan": subscription_plan,
                "user_subscriptions_count": user_subscriptions_count,
            },
        )
