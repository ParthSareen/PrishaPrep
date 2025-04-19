import requests
import json
import websockets
import asyncio
import pytest
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

class TestInventorySystem:
    def setup_method(self):
        self.session = requests.Session()
        self.token = self.authenticate()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def authenticate(self):
        response = requests.post(
            f"{BASE_URL}/token",
            data={"username": "test_user", "password": "test_password"}
        )
        return response.json()["access_token"]

    def test_product_management(self):
        # Create a product
        product_data = {
            "name": "Test Product",
            "description": "Test Description",
            "sku": "TEST-001",
            "category": "Test Category"
        }
        response = self.session.post(f"{BASE_URL}/products/", json=product_data)
        product_id = response.json()["id"]
        assert response.status_code == 200

        # Create product variant
        variant_data = {
            "product_id": product_id,
            "name": "Test Variant",
            "sku": "TEST-001-V1",
            "attributes": {"color": "red", "size": "M"}
        }
        response = self.session.post(f"{BASE_URL}/products/variants/", json=variant_data)
        assert response.status_code == 200

    def test_warehouse_management(self):
        # Create warehouse
        warehouse_data = {
            "name": "Test Warehouse",
            "location": "Test Location",
            "capacity": 1000
        }
        response = self.session.post(f"{BASE_URL}/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["id"]
        assert response.status_code == 200

        # Update inventory
        inventory_data = {
            "warehouse_id": warehouse_id,
            "quantity": 100,
            "low_stock_threshold": 20
        }
        response = self.session.post(f"{BASE_URL}/inventory/1/update", json=inventory_data)
        assert response.status_code == 200

    def test_order_processing(self):
        # Create order
        order_data = {
            "customer_id": 1,
            "warehouse_id": 1,
            "items": [
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 1}
            ]
        }
        response = self.session.post(f"{BASE_URL}/orders/", json=order_data)
        order_id = response.json()["id"]
        assert response.status_code == 200

        # Check order status
        response = self.session.get(f"{BASE_URL}/orders/{order_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"

    def test_backorder_handling(self):
        # Create backorder
        backorder_data = {
            "product_id": 1,
            "customer_id": 1,
            "quantity": 5,
            "expected_date": (datetime.now() + timedelta(days=7)).isoformat()
        }
        response = self.session.post(f"{BASE_URL}/backorders/", json=backorder_data)
        assert response.status_code == 200

    def test_inventory_transfer(self):
        # Transfer inventory between warehouses
        transfer_data = {
            "from_warehouse_id": 1,
            "to_warehouse_id": 2,
            "product_id": 1,
            "quantity": 10
        }
        response = self.session.post(f"{BASE_URL}/warehouses/1/transfer", json=transfer_data)
        assert response.status_code == 200

    def test_analytics(self):
        # Get inventory analytics
        response = self.session.get(f"{BASE_URL}/analytics/inventory")
        assert response.status_code == 200
        assert "total_products" in response.json()
        assert "low_stock_items" in response.json()

async def test_websocket():
    async with websockets.connect("ws://localhost:8000/ws") as websocket:
        # Create a product with low stock
        product_data = {
            "name": "Low Stock Product",
            "description": "Test Description",
            "sku": "LOW-001",
            "category": "Test Category"
        }
        response = requests.post(f"{BASE_URL}/products/", json=product_data)
        product_id = response.json()["id"]

        # Update inventory to trigger low stock alert
        inventory_data = {
            "warehouse_id": 1,
            "quantity": 5,
            "low_stock_threshold": 10
        }
        requests.post(f"{BASE_URL}/inventory/{product_id}/update", json=inventory_data)

        # Wait for WebSocket message
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "low_stock_alert"
        assert data["product_id"] == product_id

if __name__ == "__main__":
    # Run REST API tests
    test_system = TestInventorySystem()
    test_system.setup_method()
    test_system.test_product_management()
    test_system.test_warehouse_management()
    test_system.test_order_processing()
    test_system.test_backorder_handling()
    test_system.test_inventory_transfer()
    test_system.test_analytics()
    
    # Run WebSocket test
    asyncio.get_event_loop().run_until_complete(test_websocket()) 