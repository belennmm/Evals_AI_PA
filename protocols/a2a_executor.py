import logging
from uuid import uuid4

from agents import Runner, RunHooks
from agents.mcp import MCPServerStreamableHttp, ToolFilterContext

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

from centralized.manager_agent import create_manager


MCP_URL = "http://127.0.0.1:8001/mcp"
SPECIALIST_TOOLS = {
    "FAQ Agent": "consultar_faq",
    "Weather Agent": "consultar_clima",
    "Safety Agent": "evaluar_condiciones",
    "Booking Agent": "crear_reserva",
}
logger = logging.getLogger("uvicorn.error")


def specialist_tool_filter(context: ToolFilterContext, tool) -> bool:
    """Solo publica la herramienta correspondiente al especialista activo."""
    return SPECIALIST_TOOLS.get(context.agent.name) == tool.name


class DelegationLogs(RunHooks):
    def __init__(self, request_id: str):
        self.request_id = request_id

    async def on_tool_start(self, context, agent, tool) -> None:
        logger.info("[A2A] Delegación iniciada request_id=%s agent=%s tool=%s",
                    self.request_id, agent.name, tool.name)

    async def on_tool_end(self, context, agent, tool, result) -> None:
        logger.info("[A2A] Delegación completada request_id=%s agent=%s tool=%s",
                    self.request_id, agent.name, tool.name)


class ParachuteAgentExecutor(AgentExecutor):
    """
    Adaptador entre A2A y el Parachute Manager.
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        request_id = uuid4().hex
        logger.info("[A2A] Mensaje recibido request_id=%s caracteres=%s",
                    request_id, len(user_input))

        if not user_input:
            response = new_text_message(
                text="No se recibió ningún mensaje."
            )
            await event_queue.enqueue_event(response)
            return

        stage = "mcp_connect"
        try:
            # Una conexión por solicitud, viva durante todo el run y sin ruta local.
            async with MCPServerStreamableHttp(
                params={"url": MCP_URL, "timeout": 10},
                name="Parachute MCP",
                cache_tools_list=True,
                client_session_timeout_seconds=120,
                tool_filter=specialist_tool_filter,
                failure_error_function=None,
                max_retry_attempts=0,
            ) as mcp_server:
                logger.info("[A2A] MCP conectado request_id=%s", request_id)
                stage = "manager_create"
                manager = create_manager(mcp_server=mcp_server)
                stage = "multiagent_run"
                logger.info("[A2A] Ejecución multiagente iniciada request_id=%s manager=%s",
                            request_id, manager.name)
                result = await Runner.run(
                    manager,
                    user_input,
                    hooks=DelegationLogs(request_id),
                )
                stage = "mcp_close"

            response = new_text_message(
                text=str(result.final_output)
            )

            await event_queue.enqueue_event(response)
            logger.info("[A2A] Respuesta enviada request_id=%s", request_id)

        except Exception as exc:
            # No imprimir el mensaje de la excepción, argumentos de tools ni salida
            # del modelo: pueden contener credenciales, cabeceras o datos personales.
            cause = type(exc.__cause__).__name__ if exc.__cause__ else "ninguna"
            logger.error("[A2A] Error request_id=%s etapa=%s tipo=%s causa=%s",
                         request_id, stage, type(exc).__name__, cause)
            error_message = (
                "No fue posible conectar con el servicio de herramientas MCP. "
                "Intenta nuevamente cuando esté disponible."
                if stage == "mcp_connect" else
                "No fue posible completar la solicitud del sistema multiagente. "
                "Consulta los registros del servidor."
            )
            response = new_text_message(
                text=error_message
            )
            await event_queue.enqueue_event(response)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        response = new_text_message(
            text="La cancelación no está disponible para este agente."
        )
        await event_queue.enqueue_event(response)
