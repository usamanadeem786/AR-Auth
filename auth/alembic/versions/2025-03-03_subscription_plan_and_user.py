"""subscription_plan_and_user

Revision ID: a64e726e5344
Revises: 78dd8ccb7398
Create Date: 2025-03-03 21:16:13.646457

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import auth

# revision identifiers, used by Alembic.
revision = "a64e726e5344"
down_revision = "78dd8ccb7398"
branch_labels = None
depends_on = None


def upgrade():
    table_prefix = op.get_context().opts["table_prefix"]
    connection = op.get_bind()
    dialect = connection.dialect.name

    # Create the enum type based on dialect
    if dialect == "postgresql":
        subscription_plan_expiry_unit_enum = postgresql.ENUM(
            "DAY",
            "DAYS",
            "MONTH",
            "MONTHS",
            "YEAR",
            "YEARS",
            name=f"{table_prefix}subscriptionplanexpiryunit",
            create_type=False,
        )
        subscription_plan_expiry_unit_enum.create(connection, checkfirst=True)
    else:
        subscription_plan_expiry_unit_enum = sa.Enum(
            "DAY",
            "DAYS",
            "MONTH",
            "MONTHS",
            "YEAR",
            "YEARS",
            name=f"{table_prefix}subscriptionplanexpiryunit",
        )

    op.create_table(
        f"{table_prefix}subscription_plans",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("granted_by_default", sa.Boolean(), nullable=False),
        sa.Column("expiry_interval", sa.Integer(), nullable=False),
        sa.Column(
            "expiry_unit",
            subscription_plan_expiry_unit_enum,
            nullable=False,
            server_default="MONTH",
        ),
        sa.Column("tenant_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("id", auth.models.generics.GUID(), nullable=False),
        sa.Column(
            "created_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{table_prefix}tenants.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_plans_tenant_id_{table_prefix}tenants"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f(f"pk_{table_prefix}subscription_plans")
        ),
        sa.UniqueConstraint(
            "name",
            "tenant_id",
            name=op.f(f"{table_prefix}subscription_plans_name_tenant_id_key"),
        ),
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscription_plans_created_at"),
        f"{table_prefix}subscription_plans",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscription_plans_expiry_unit"),
        f"{table_prefix}subscription_plans",
        ["expiry_unit"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscription_plans_updated_at"),
        f"{table_prefix}subscription_plans",
        ["updated_at"],
        unique=False,
    )
    op.create_table(
        f"{table_prefix}subscription_plan_roles",
        sa.Column("subscription_plan_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("role_id", auth.models.generics.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            [f"{table_prefix}roles.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_plan_roles_role_id_{table_prefix}roles"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_plan_id"],
            [f"{table_prefix}subscription_plans.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_plan_roles_subscription_plan_id_{table_prefix}subscription_plans"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "subscription_plan_id",
            "role_id",
            name=op.f(f"pk_{table_prefix}subscription_plan_roles"),
        ),
    )
    op.create_table(
        f"{table_prefix}user_subscriptions",
        sa.Column("user_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("subscription_plan_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("id", auth.models.generics.GUID(), nullable=False),
        sa.Column(
            "created_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_plan_id"],
            [f"{table_prefix}subscription_plans.id"],
            name=op.f(
                f"fk_{table_prefix}user_subscriptions_subscription_plan_id_{table_prefix}subscription_plans"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{table_prefix}users.id"],
            name=op.f(
                f"fk_{table_prefix}user_subscriptions_user_id_{table_prefix}users"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f(f"pk_{table_prefix}user_subscriptions")
        ),
        sa.UniqueConstraint(
            "user_id",
            "subscription_plan_id",
            name=op.f(
                f"{table_prefix}user_subscriptions_user_id_subscription_plan_id_key"
            ),
        ),
    )
    op.create_index(
        op.f(f"ix_{table_prefix}user_subscriptions_created_at"),
        f"{table_prefix}user_subscriptions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}user_subscriptions_expires_at"),
        f"{table_prefix}user_subscriptions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}user_subscriptions_updated_at"),
        f"{table_prefix}user_subscriptions",
        ["updated_at"],
        unique=False,
    )
    op.drop_constraint(
        f"{table_prefix}organization_invitations_token_key",
        f"{table_prefix}organization_invitations",
        type_="unique",
    )
    # ### end Alembic commands ###


def downgrade():
    table_prefix = op.get_context().opts["table_prefix"]
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        f"{table_prefix}organization_invitations_token_key",
        f"{table_prefix}organization_invitations",
        ["token"],
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}user_subscriptions_updated_at"),
        table_name=f"{table_prefix}user_subscriptions",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}user_subscriptions_expires_at"),
        table_name=f"{table_prefix}user_subscriptions",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}user_subscriptions_created_at"),
        table_name=f"{table_prefix}user_subscriptions",
    )
    op.drop_table(f"{table_prefix}user_subscriptions")
    op.drop_table(f"{table_prefix}subscription_plan_roles")
    op.drop_index(
        op.f(f"ix_{table_prefix}subscription_plans_updated_at"),
        table_name=f"{table_prefix}subscription_plans",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}subscription_plans_expiry_unit"),
        table_name=f"{table_prefix}subscription_plans",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}subscription_plans_created_at"),
        table_name=f"{table_prefix}subscription_plans",
    )
    op.drop_table(f"{table_prefix}subscription_plans")
    # ### end Alembic commands ###
