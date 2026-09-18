from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import time

class InstanceStatus(str, Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"

class LoadBalanceStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_conn"
    WEIGHTED = "weighted"

class ServiceInstance(BaseModel):
    instance_id: str = Field(..., description="Unique ID for instance, e.g. service_a_8001")
    service_name: str = Field(..., description="Name of the service group, e.g. service_a")
    host: str = Field(..., description="Host IP or hostname, e.g. 127.0.0.1 or service-a-1")
    port: int = Field(..., description="Port number, e.g. 8001")
    status: InstanceStatus = Field(default=InstanceStatus.HEALTHY, description="Current health status")
    last_heartbeat: float = Field(default_factory=time.time, description="Timestamp of last heartbeat in seconds")
    weight: int = Field(default=1, ge=1, description="Weight for weighted load balancing")
    active_connections: int = Field(default=0, ge=0, description="Active connection counter for least connection LB")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata tags")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_contract_dict(self) -> Dict[str, Any]:
        """Returns exact dictionary format specified in project contract."""
        return {
            "instance_id": self.instance_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "status": self.status.value if isinstance(self.status, InstanceStatus) else self.status,
            "last_heartbeat": self.last_heartbeat,
            "weight": self.weight,
            "active_connections": self.active_connections,
            "url": self.url
        }

class RegisterRequest(BaseModel):
    service_name: str
    host: str
    port: int
    instance_id: Optional[str] = None
    weight: Optional[int] = 1
    metadata: Optional[Dict[str, Any]] = None

class DeregisterRequest(BaseModel):
    service_name: str
    instance_id: str

class HeartbeatRequest(BaseModel):
    service_name: str
    instance_id: str

class StatusUpdateRequest(BaseModel):
    status: InstanceStatus
    reason: Optional[str] = None
