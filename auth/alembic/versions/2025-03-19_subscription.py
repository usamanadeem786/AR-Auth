"""subscription

Revision ID: 9b1f92b6b44e
Revises: 78dd8ccb7398
Create Date: 2025-03-19 19:42:48.127910

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import auth

# revision identifiers, used by Alembic.
revision = "9b1f92b6b44e"
down_revision = "78dd8ccb7398"
branch_labels = None
depends_on = None


def upgrade():
    table_prefix = op.get_context().opts["table_prefix"]
    connection = op.get_bind()
    dialect = connection.dialect.name

    # Create the enum types based on dialect
    if dialect == "postgresql":
        subscriptiontier_mode_enum = postgresql.ENUM(
            "RECURRING",
            "ONE_TIME",
            name=f"{table_prefix}subscriptiontier_mode",
            create_type=False,
        )
        subscriptiontier_mode_enum.create(connection, checkfirst=True)

        subscriptiontier_type_enum = postgresql.ENUM(
            "PRIMARY",
            "ADD_ON",
            name=f"{table_prefix}subscriptiontier_type",
            create_type=False,
        )
        subscriptiontier_type_enum.create(connection, checkfirst=True)

        subscription_interval_enum = postgresql.ENUM(
            "DAY",
            "MONTH",
            "YEAR",
            name=f"{table_prefix}subscription_interval",
            create_type=False,
        )
        subscription_interval_enum.create(connection, checkfirst=True)

        subscription_status_enum = postgresql.ENUM(
            "PENDING",
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "TRIALING",
            "EXPIRED",
            name=f"{table_prefix}subscription_status",
            create_type=False,
        )
        subscription_status_enum.create(connection, checkfirst=True)

    else:
        # For non-PostgreSQL dialects, use standard SQLAlchemy Enum
        subscriptiontier_mode_enum = sa.Enum(
            "RECURRING",
            "ONE_TIME",
            name=f"{table_prefix}subscriptionmode",
        )

        subscriptiontier_type_enum = sa.Enum(
            "PRIMARY",
            "ADD_ON",
            name=f"{table_prefix}subscriptiontier_type",
        )

        subscription_interval_enum = sa.Enum(
            "DAY",
            "MONTH",
            "YEAR",
            name=f"{table_prefix}subscription_interval",
        )

        subscription_status_enum = sa.Enum(
            "PENDING",
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "TRIALING",
            "EXPIRED",
            name=f"{table_prefix}subscription_status",
        )

    op.create_table(
        f"{table_prefix}subscriptions",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("stripe_product_id", sa.String(length=255), nullable=False),
        sa.Column("accounts", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
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
                f"fk_{table_prefix}subscriptions_tenant_id_{table_prefix}tenants"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_prefix}subscriptions")),
        sa.UniqueConstraint(
            "stripe_product_id",
            name=op.f(f"{table_prefix}subscriptions_stripe_product_id_key"),
        ),
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscriptions_created_at"),
        f"{table_prefix}subscriptions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscriptions_updated_at"),
        f"{table_prefix}subscriptions",
        ["updated_at"],
        unique=False,
    )
    op.create_table(
        f"{table_prefix}subscription_roles",
        sa.Column("subscription_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("role_id", auth.models.generics.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            [f"{table_prefix}roles.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_roles_role_id_{table_prefix}roles"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            [f"{table_prefix}subscriptions.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_roles_subscription_id_{table_prefix}subscriptions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "subscription_id",
            "role_id",
            name=op.f(f"pk_{table_prefix}subscription_roles"),
        ),
    )
    op.create_table(
        f"{table_prefix}subscription_tiers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subscription_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=False),
        sa.Column(
            "mode",
            subscriptiontier_mode_enum,
            nullable=False,
            server_default="RECURRING",
        ),
        sa.Column(
            "type",
            subscriptiontier_type_enum,
            nullable=True,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "interval",
            subscription_interval_enum,
            nullable=True,
            server_default="MONTH",
        ),
        sa.Column("interval_count", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
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
            ["subscription_id"],
            [f"{table_prefix}subscriptions.id"],
            name=op.f(
                f"fk_{table_prefix}subscription_tiers_subscription_id_{table_prefix}subscriptions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f(f"pk_{table_prefix}subscription_tiers")
        ),
        sa.UniqueConstraint(
            "stripe_price_id",
            name=op.f(f"{table_prefix}subscription_tiers_stripe_price_id_key"),
        ),
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscription_tiers_created_at"),
        f"{table_prefix}subscription_tiers",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}subscription_tiers_updated_at"),
        f"{table_prefix}subscription_tiers",
        ["updated_at"],
        unique=False,
    )
    op.create_table(
        f"{table_prefix}organization_subscriptions",
        sa.Column("tier_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("organization_id", auth.models.generics.GUID(), nullable=False),
        sa.Column("accounts", sa.Integer(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=False),
        sa.Column(
            "expires_at",
            auth.models.generics.TIMESTAMPAware(timezone=True),
            nullable=True,
        ),
        sa.Column("grace_period", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "interval",
            subscription_interval_enum,
            nullable=True,
            server_default="MONTH",
        ),
        sa.Column("interval_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            subscription_status_enum,
            nullable=False,
            server_default="PENDING",
        ),
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
            ["organization_id"],
            [f"{table_prefix}organizations.id"],
            name=op.f(
                f"fk_{table_prefix}organization_subscriptions_organization_id_{table_prefix}organizations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tier_id"],
            [f"{table_prefix}subscription_tiers.id"],
            name=op.f(
                f"fk_{table_prefix}organization_subscriptions_tier_id_{table_prefix}subscription_tiers"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f(f"pk_{table_prefix}organization_subscriptions")
        ),
        sa.UniqueConstraint(
            "organization_id",
            "tier_id",
            "stripe_subscription_id",
            "status",
            name=op.f(
                f"{table_prefix}organization_subscriptions_organization_id_tier_id_stripe_subscription_id_status_key"
            ),
        ),
    )
    op.create_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_created_at"),
        f"{table_prefix}organization_subscriptions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_expires_at"),
        f"{table_prefix}organization_subscriptions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_updated_at"),
        f"{table_prefix}organization_subscriptions",
        ["updated_at"],
        unique=False,
    )
    op.create_table(
        f"{table_prefix}organization_subscription_roles",
        sa.Column(
            "organization_subscription_id", auth.models.generics.GUID(), nullable=False
        ),
        sa.Column("role_id", auth.models.generics.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_subscription_id"],
            [f"{table_prefix}organization_subscriptions.id"],
            name=op.f(
                f"fk_{table_prefix}organization_subscription_roles_organization_subscription_id_{table_prefix}organization_subscriptions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            [f"{table_prefix}roles.id"],
            name=op.f(
                f"fk_{table_prefix}organization_subscription_roles_role_id_{table_prefix}roles"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_subscription_id",
            "role_id",
            name=op.f(f"pk_{table_prefix}organization_subscription_roles"),
        ),
    )
    op.drop_constraint(
        f"{table_prefix}organization_invitations_token_key",
        f"{table_prefix}organization_invitations",
        type_="unique",
    )
    op.add_column(
        f"{table_prefix}permissions",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        f"{table_prefix}roles",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        f"{table_prefix}users",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    table_prefix = op.get_context().opts["table_prefix"]
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column(f"{table_prefix}users", "stripe_customer_id")
    op.drop_column(f"{table_prefix}roles", "is_public")
    op.drop_column(f"{table_prefix}permissions", "is_public")
    op.create_unique_constraint(
        f"{table_prefix}organization_invitations_token_key",
        f"{table_prefix}organization_invitations",
        ["token"],
    )
    op.drop_table(f"{table_prefix}organization_subscription_roles")
    op.drop_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_updated_at"),
        table_name=f"{table_prefix}organization_subscriptions",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_expires_at"),
        table_name=f"{table_prefix}organization_subscriptions",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}organization_subscriptions_created_at"),
        table_name=f"{table_prefix}organization_subscriptions",
    )
    op.drop_table(f"{table_prefix}organization_subscriptions")
    op.drop_index(
        op.f(f"ix_{table_prefix}subscription_tiers_updated_at"),
        table_name=f"{table_prefix}subscription_tiers",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}subscription_tiers_created_at"),
        table_name=f"{table_prefix}subscription_tiers",
    )
    op.drop_table(f"{table_prefix}subscription_tiers")
    op.drop_table(f"{table_prefix}subscription_roles")
    op.drop_index(
        op.f(f"ix_{table_prefix}subscriptions_updated_at"),
        table_name=f"{table_prefix}subscriptions",
    )
    op.drop_index(
        op.f(f"ix_{table_prefix}subscriptions_created_at"),
        table_name=f"{table_prefix}subscriptions",
    )
    op.drop_table(f"{table_prefix}subscriptions")
    # ### end Alembic commands ###
