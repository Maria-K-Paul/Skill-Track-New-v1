import asyncio
import httpx
import pytest
from datetime import datetime, timedelta, timezone

API_URL = "http://localhost:8002"

@pytest.mark.asyncio
async def test_duplicate_slots():
    async with httpx.AsyncClient(base_url=API_URL) as client:
        # Login admin
        resp = await client.post("/auth/login", json={"email": "admin@college.edu", "password": "Password@123"})
        admin_token = resp.json()["access_token"]

        # Login owner
        resp = await client.post("/auth/login", json={"email": "owner@college.edu", "password": "Password@123"})
        owner_token = resp.json()["access_token"]
        
        starts_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        slot_data = {"level_id": 1, "starts_at": starts_at, "venue": "Room 101", "capacity": 30}
        
        # 1. Admin creates Slot A
        r1 = await client.post("/manage/slots", json=slot_data, headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Admin create slot: {r1.status_code}")
        
        # 2. Owner creates same Slot A
        r2 = await client.post("/manage/slots", json=slot_data, headers={"Authorization": f"Bearer {owner_token}"})
        print(f"Owner create slot: {r2.status_code} (Expected 409)")

        # 3. Concurrent creates
        slot_data_b = {"level_id": 1, "starts_at": starts_at, "venue": "Room 102", "capacity": 30}
        
        async def create_slot():
            return await client.post("/manage/slots", json=slot_data_b, headers={"Authorization": f"Bearer {admin_token}"})

        results = await asyncio.gather(*[create_slot() for _ in range(10)])
        statuses = [r.status_code for r in results]
        print(f"Concurrent creates statuses: {statuses}")
        assert statuses.count(201) == 1
        assert statuses.count(409) == 9

if __name__ == "__main__":
    asyncio.run(test_duplicate_slots())
