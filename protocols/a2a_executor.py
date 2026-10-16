from agents import Runner

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

from centralized.manager_agent import create_manager


class ParachuteAgentExecutor(AgentExecutor):
    """
    Adaptador entre A2A y el Parachute Manager.
    """

    def __init__(self):
        self.manager = create_manager()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()

        if not user_input:
            response = new_text_message(
                text="No se recibió ningún mensaje."
            )
            await event_queue.enqueue_event(response)
            return

        try:
            result = await Runner.run(
                self.manager,
                user_input,
            )

            response = new_text_message(
                text=str(result.final_output)
            )

            await event_queue.enqueue_event(response)

        except Exception as exc:
            response = new_text_message(
                text=f"Error al procesar la solicitud: {exc}"
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