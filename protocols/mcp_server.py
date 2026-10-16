"""Único servidor MCP de negocio. Ejecutar: python -m protocols.mcp_server."""
import asyncio
import json
import logging
import os
from pathlib import Path
from threading import Lock
from time import perf_counter

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# knowledge_tool lee DB_* durante su importación.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from centralized import booking_agent, faq_agent, safety_agent, weather_agent

logger = logging.getLogger("parachute.mcp")
_booking_lock = Lock()


async def _invoke(name, operation, *args, **safe_params) -> str:
    started = perf_counter()
    logger.info("[MCP] Herramienta solicitada tool=%s params=%s", name,
                json.dumps(safe_params, ensure_ascii=False))
    try:
        result = await asyncio.to_thread(operation, *args)
    except Exception as error:
        # No registrar excepciones arbitrarias: pueden contener credenciales DB/API.
        logger.error("[MCP] Herramienta error tool=%s tipo=%s", name, type(error).__name__)
        raise ToolError(f"No fue posible ejecutar {name}. Revise el servidor MCP.") from None
    failed = result.startswith(("ERROR_CLIMA:", "ERROR_SEGURIDAD:",
                                "No fue posible consultar la base de conocimiento."))
    logger.info("[MCP] Herramienta %s tool=%s duration_ms=%.0f",
                "error" if failed else "completada", name, (perf_counter() - started) * 1000)
    return result


def _reserve(fecha: str, seguridad_json: str) -> str:
    # El calendario original sigue siendo la misma lista; serializar la operación
    # evita duplicados al atender dos peticiones HTTP simultáneas.
    with _booking_lock:
        return booking_agent.reservar_local(fecha, seguridad_json)


def create_server() -> MCPServer:
    server = MCPServer(name="Parachute Business Tools", version="1.0.0")

    @server.tool(structured_output=False)
    async def consultar_faq(pregunta: str) -> str:
        """Busca una respuesta en la base de FAQs de Parachute S.A."""
        return await _invoke("consultar_faq", faq_agent.resolver_faq, pregunta,
                             pregunta_longitud=len(pregunta))

    @server.tool(structured_output=False)
    async def consultar_clima(fecha: str) -> str:
        """Obtiene el pronóstico agregado de Parachute S.A. para YYYY-MM-DD."""
        return await _invoke("consultar_clima", weather_agent.resolver_clima, fecha, fecha=fecha)

    @server.tool(structured_output=False)
    async def evaluar_condiciones(
        fecha: str,
        temperatura_2m: float,
        precipitacion: float,
        cobertura_nubes: float,
        velocidad_viento: float,
        rachas_viento: float,
    ) -> str:
        """Evalúa clima estructurado y devuelve estado IDEAL, MARGINAL o PROHIBIDO."""
        return await _invoke(
            "evaluar_condiciones", safety_agent.resolver_seguridad,
            fecha, temperatura_2m, precipitacion, cobertura_nubes, velocidad_viento, rachas_viento,
            fecha=fecha, temperatura_2m=temperatura_2m, precipitacion=precipitacion,
            cobertura_nubes=cobertura_nubes, velocidad_viento=velocidad_viento,
            rachas_viento=rachas_viento,
        )

    @server.tool(structured_output=False)
    async def crear_reserva(fecha: str, seguridad_json: str) -> str:
        """Crea una reserva local después de una evaluación de seguridad válida."""
        return await _invoke("crear_reserva", _reserve, fecha, seguridad_json, fecha=fecha)

    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8001"))
    server = create_server()
    # Esta línea anuncia la configuración, no readiness: el bind ocurre en run().
    logger.info("[MCP] Iniciando servidor transport=streamable-http")
    logger.info("[MCP] Endpoint configurado http://%s:%s/mcp", host, port)
    server.run(transport="streamable-http", host=host, port=port,
               streamable_http_path="/mcp", json_response=True, stateless_http=True)


if __name__ == "__main__":
    main()
