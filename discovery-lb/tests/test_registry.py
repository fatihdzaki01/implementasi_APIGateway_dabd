import pytest
import asyncio
import time
from app.registry import ServiceRegistry
from app.models import RegisterRequest, InstanceStatus

@pytest.mark.asyncio
async def test_register_and_get_instance():
    reg = ServiceRegistry()
    req = RegisterRequest(service_name="payment", host="127.0.0.1", port=8001, instance_id="payment_1")
    
    inst = await reg.register(req)
    assert inst.instance_id == "payment_1"
    assert inst.service_name == "payment"
    assert inst.host == "127.0.0.1"
    assert inst.port == 8001
    assert inst.status == InstanceStatus.HEALTHY

    all_inst = await reg.get_instances("payment")
    assert len(all_inst) == 1
    assert all_inst[0].instance_id == "payment_1"

@pytest.mark.asyncio
async def test_deregister_instance():
    reg = ServiceRegistry()
    req = RegisterRequest(service_name="payment", host="127.0.0.1", port=8001, instance_id="payment_1")
    await reg.register(req)

    success = await reg.deregister("payment", "payment_1")
    assert success is True

    instances = await reg.get_instances("payment")
    assert len(instances) == 0

@pytest.mark.asyncio
async def test_update_status_from_health_checker():
    reg = ServiceRegistry()
    req = RegisterRequest(service_name="user_service", host="127.0.0.1", port=8002, instance_id="user_1")
    await reg.register(req)

    # Orang 3 marks instance as UNHEALTHY
    updated = await reg.update_status("user_service", "user_1", InstanceStatus.UNHEALTHY)
    assert updated is True

    healthy = await reg.get_instances("user_service", healthy_only=True)
    assert len(healthy) == 0

    all_instances = await reg.get_instances("user_service", healthy_only=False)
    assert len(all_instances) == 1
    assert all_instances[0].status == InstanceStatus.UNHEALTHY

@pytest.mark.asyncio
async def test_heartbeat_cleanup():
    reg = ServiceRegistry()
    req = RegisterRequest(service_name="catalog", host="127.0.0.1", port=8003, instance_id="cat_1")
    inst = await reg.register(req)
    
    # Simulate old heartbeat (expired 20 seconds ago)
    inst.last_heartbeat = time.time() - 20

    removed = await reg.cleanup_stale_instances(ttl_seconds=10)
    assert "cat_1" in removed

    remaining = await reg.get_instances("catalog", healthy_only=False)
    assert len(remaining) == 0
