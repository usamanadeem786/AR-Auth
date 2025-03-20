# from fastapi import APIRouter, Depends, Header, Request
# from fastapi.exceptions import HTTPException
# from pydantic import UUID4

# from auth.apps.dashboard.dependencies import BaseContext, get_base_context
# from auth.dependencies.admin_authentication import \
#     is_authenticated_admin_session
# from auth.dependencies.organizations import OrganizationRepository
# from auth.dependencies.repositories import get_repository
# from auth.dependencies.users import get_user_by_id_or_404
# from auth.templates import templates

# router = APIRouter(dependencies=[Depends(is_authenticated_admin_session)])


# # Organization endpoints
# @router.get("/", name="dashboard.organizations:list")
# async def list_organizations(
#     request: Request,
#     query: str = None,
#     organization_repository: OrganizationRepository = Depends(
#         get_repository(OrganizationRepository)
#     ),
#     context: BaseContext = Depends(get_base_context),
#     hx_combobox: bool = Header(False),
# ):
#     # Get all active prices
#     organizations = await organization_repository.all()

#     # Filter by query if provided
#     if query:
#         organizations = [
#             organization
#             for organization in organizations
#             if query.lower() in organization.name.lower()
#         ]

#     if hx_combobox:
#         return templates.TemplateResponse(
#             request,
#             "admin/organizations/list_combobox.html",
#             {
#                 **context,
#                 "organizations": organizations,
#             },
#         )

#     # For now, just return the combobox view
#     return templates.TemplateResponse(
#         request,
#         "admin/subscriptions/prices/list_combobox.html",
#         {
#             **context,
#             "organizations": organizations,
#         },
#     )
