import pytest
from django.db import ProgrammingError, connection, transaction

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.inventory.models import InventoryItem, StockMovement
from apps.tenancy.context import activate_organization


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_stock_movement_updates_quantity_on_hand_and_rejects_overdraw(
    api_client, organization, user_factory, school_factory, inventory_item_factory,
):
    school = school_factory(organization=organization)
    item = inventory_item_factory(school=school, quantity_on_hand=5)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "stock_movements.view", "stock_movements.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    stock_in = api_client.post(
        "/api/v1/stock-movements",
        {"item": str(item.public_id), "movement_type": "in", "quantity": 10},
        format="json",
    )
    assert stock_in.status_code == 201
    item.refresh_from_db()
    assert item.quantity_on_hand == 15

    stock_out = api_client.post(
        "/api/v1/stock-movements",
        {"item": str(item.public_id), "movement_type": "out", "quantity": -3},
        format="json",
    )
    assert stock_out.status_code == 201
    item.refresh_from_db()
    assert item.quantity_on_hand == 12

    overdraw = api_client.post(
        "/api/v1/stock-movements",
        {"item": str(item.public_id), "movement_type": "out", "quantity": -1000},
        format="json",
    )
    assert overdraw.status_code == 409

    wrong_sign = api_client.post(
        "/api/v1/stock-movements",
        {"item": str(item.public_id), "movement_type": "in", "quantity": -5},
        format="json",
    )
    assert wrong_sign.status_code == 409


@pytest.mark.django_db
def test_purchase_order_receive_posts_stock_movement_and_updates_quantity(
    api_client, organization, user_factory, school_factory, inventory_item_factory,
    supplier_factory, purchase_order_factory,
):
    school = school_factory(organization=organization)
    item = inventory_item_factory(school=school, quantity_on_hand=0)
    supplier = supplier_factory(school=school)
    purchase_order = purchase_order_factory(item=item, supplier=supplier, quantity_ordered=20)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "purchase_orders.view", "purchase_orders.update", "purchase_orders.receive")
    _login(api_client, "a@example.com", "s3cret-pass!")

    ordered = api_client.post(f"/api/v1/purchase-orders/{purchase_order.public_id}/mark-ordered")
    assert ordered.status_code == 200
    assert ordered.json()["data"]["status"] == "ordered"

    received = api_client.post(f"/api/v1/purchase-orders/{purchase_order.public_id}/receive")
    assert received.status_code == 200
    assert received.json()["data"]["status"] == "received"

    item.refresh_from_db()
    assert item.quantity_on_hand == 20

    double_receive = api_client.post(f"/api/v1/purchase-orders/{purchase_order.public_id}/receive")
    assert double_receive.status_code == 409


@pytest.mark.django_db
def test_inventory_app_layer_tenant_isolation(organization, other_organization, school_factory, inventory_item_factory):
    inventory_item_factory(school=school_factory(organization=organization))
    inventory_item_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    visible = InventoryItem.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.skipif(connection.vendor != "postgresql", reason="append-only trigger is Postgres-only")
@pytest.mark.django_db
def test_stock_movement_is_append_only_at_db_level(organization, school_factory, inventory_item_factory):
    school = school_factory(organization=organization)
    item = inventory_item_factory(school=school)
    activate_organization(organization.id)
    from django.utils import timezone

    movement = StockMovement.all_tenants.create(
        organization=organization, item=item, movement_type="in", quantity=10, occurred_at=timezone.now()
    )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE inventory_stock_movement SET quantity = %s WHERE id = %s", [999, movement.id]
                )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM inventory_stock_movement WHERE id = %s", [movement.id])
