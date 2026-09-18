import pytest
import asyncio
from app.registry import ServiceRegistry
from app.load_balancer import LoadBalancer, NoHealthyInstanceException
from app.models import RegisterRequest, InstanceStatus, LoadBalanceStrategy

@pytest.mark.asyncio
async def test_round_robin_distribution():
    reg = ServiceRegistry()
    lb = LoadBalancer(reg)

    # Register 3 instances
    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8001, instance_id="ord_1"))
    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8002, instance_id="ord_2"))
    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8003, instance_id="ord_3"))

    # Sequence of 6 requests must cycle 1 -> 2 -> 3 -> 1 -> 2 -> 3
    selected_ids = []
    for _ in range(6):
        inst = await lb.select_instance("order_service", strategy=LoadBalanceStrategy.ROUND_ROBIN)
        selected_ids.append(inst.instance_id)

    assert selected_ids == ["ord_1", "ord_2", "ord_3", "ord_1", "ord_2", "ord_3"]

@pytest.mark.asyncio
async def test_round_robin_skips_unhealthy_instances():
    reg = ServiceRegistry()
    lb = LoadBalancer(reg)

    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8001, instance_id="ord_1"))
    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8002, instance_id="ord_2"))
    await reg.register(RegisterRequest(service_name="order_service", host="127.0.0.1", port=8003, instance_id="ord_3"))

    # Mark ord_2 as UNHEALTHY (e.g. by Orang 3 Health Checker)
    await reg.update_status("order_service", "ord_2", InstanceStatus.UNHEALTHY)

    # Sequence of 4 requests must cycle only between healthy instances (ord_1 and ord_3)
    selected_ids = []
    for _ in range(4):
        inst = await lb.select_instance("order_service", strategy=LoadBalanceStrategy.ROUND_ROBIN)
        selected_ids.append(inst.instance_id)

    assert "ord_2" not in selected_ids
    assert selected_ids == ["ord_1", "ord_3", "ord_1", "ord_3"]

@pytest.mark.asyncio
async def test_no_healthy_instances_exception():
    reg = ServiceRegistry()
    lb = LoadBalancer(reg)

    await reg.register(RegisterRequest(service_name="auth", host="127.0.0.1", port=8001, instance_id="auth_1"))
    await reg.update_status("auth", "auth_1", InstanceStatus.UNHEALTHY)

    with pytest.raises(NoHealthyInstanceException):
        await lb.select_instance("auth", strategy=LoadBalanceStrategy.ROUND_ROBIN)

@pytest.mark.asyncio
async def test_least_connections_strategy():
    reg = ServiceRegistry()
    lb = LoadBalancer(reg)

    inst1 = await reg.register(RegisterRequest(service_name="search", host="127.0.0.1", port=8001, instance_id="s1"))
    inst2 = await reg.register(RegisterRequest(service_name="search", host="127.0.0.1", port=8002, instance_id="s2"))

    inst1.active_connections = 10
    inst2.active_connections = 2

    # Should pick s2 because active_connections (2) < (10)
    selected = await lb.select_instance("search", strategy=LoadBalanceStrategy.LEAST_CONNECTIONS)
    assert selected.instance_id == "s2"
