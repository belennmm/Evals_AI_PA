import uvicorn

from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes

from protocols.agent_card import AGENT_CARD
from protocols.a2a_executor import ParachuteAgentExecutor


HOST = "127.0.0.1"
PORT = 8000


def create_app() -> Starlette:
    executor = ParachuteAgentExecutor()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=AGENT_CARD,
    )

    routes = []

    routes.extend(
        create_agent_card_routes(
            agent_card=AGENT_CARD,
        )
    )

    routes.extend(
        create_jsonrpc_routes(
            request_handler=request_handler,
            rpc_url="/",
        )
    )

    app = Starlette(
        routes=routes,
    )

    return app


app = create_app()


def main():
    print("Iniciando servidor A2A")
    print(
        f"Agent Card: "
        f"http://{HOST}:{PORT}/.well-known/agent-card.json"
    )
    print(
        f"Endpoint JSON-RPC: "
        f"http://{HOST}:{PORT}/"
    )

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
    )


if __name__ == "__main__":
    main()