import logging
import httpx

logger = logging.getLogger("resilience.health_checker")


async def check_health(host: str, port: int, timeout: float = 2.0) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code == 200
    except httpx.TimeoutException:
        logger.debug(f"[HEALTH] {url} → timeout")
        return False
    except Exception as e:
        logger.debug(f"[HEALTH] {url} → {type(e).__name__}: {e}")
        return False
