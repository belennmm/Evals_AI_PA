"""Terminal A2A. Ejecutar: python -m protocols.terminal_client."""
import asyncio
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientTimeoutError, AgentCardResolutionError
from a2a.helpers import get_message_text, get_stream_response_text, new_text_message
from a2a.types import Role, SendMessageRequest
from a2a.utils.errors import A2AError


A2A_URL = "http://127.0.0.1:8000"
EXIT_COMMANDS = {"salir", "exit", "quit"}


async def send_question(client: Client, text: str, context_id: str) -> str:
    """Envía un mensaje A2A con ID nuevo y el contexto de la sesión actual."""
    request = SendMessageRequest(
        message=new_text_message(
            text=text,
            role=Role.ROLE_USER,
            context_id=context_id,
        )
    )
    answers = []
    async for event in client.send_message(request):
        answer = get_stream_response_text(event)
        if not answer and event.HasField("task") and event.task.status.HasField("message"):
            answer = get_message_text(event.task.status.message)
        if answer:
            answers.append(answer)
    return "\n".join(answers) or "El agente no devolvió una respuesta de texto."


async def run_client() -> int:
    context_id = str(uuid4())
    # El cliente HTTP es solo para A2A local. No hereda proxies del entorno.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(300, connect=5),
        trust_env=False,
        headers={"A2A-Version": "1.0"},
    ) as http_client:
        try:
            card = await A2ACardResolver(
                httpx_client=http_client, base_url=A2A_URL,
            ).get_agent_card()
            client = ClientFactory(ClientConfig(
                httpx_client=http_client,
                streaming=False,
                supported_protocol_bindings=["JSONRPC"],
                accepted_output_modes=["text/plain"],
            )).create(card)
        except (AgentCardResolutionError, httpx.RequestError, A2AError, ValueError) as error:
            print(f"No fue posible conectar con A2A u obtener una Agent Card compatible en {A2A_URL}.")
            print(f"Comprueba que el servidor esté iniciado. Tipo de error: {type(error).__name__}.")
            return 1

        async with client:
            print(f"[Cliente A2A] Agent Card obtenida: {card.name}")
            print(f"[Cliente A2A] Conectado a {A2A_URL} mediante JSON-RPC A2A 1.0")
            print(f"[Cliente A2A] Contexto de sesión: {context_id}")
            print("Escribe salir, exit o quit para terminar.")
            while True:
                try:
                    text = input("\nTú: ").strip()
                except EOFError:
                    break
                if text.lower() in EXIT_COMMANDS:
                    break
                if not text:
                    continue
                try:
                    answer = await send_question(client, text, context_id)
                    print(f"\nParachute: {answer}")
                except (httpx.TimeoutException, A2AClientTimeoutError):
                    print("Tiempo de espera agotado. La solicitud no se reenvió automáticamente; "
                          "comprueba su resultado antes de volver a enviarla.")
                except (httpx.RequestError, A2AError) as error:
                    print("No fue posible completar la comunicación con A2A. "
                          f"Revisa el servidor. Tipo de error: {type(error).__name__}.")
            print("Hasta luego.")
    return 0


def main() -> int:
    try:
        return asyncio.run(run_client())
    except KeyboardInterrupt:
        print("\nHasta luego.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
