from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentInterface,
    AgentSkill,
)


A2A_URL = "http://127.0.0.1:8000"


def create_agent_card() -> AgentCard:
    """
    Crea la Agent Card publica de Parachute Assistant.
    """

    information_skill = AgentSkill(
        id="information_queries",
        name="Consultas de informacion",
        description=(
            "Responde preguntas frecuentes y consulta informacion "
            "meteorologica para una fecha indicada."
        ),
        tags=[
            "faq",
            "clima",
            "informacion",
        ],
        examples=[
            "¿Que necesito para hacer paracaidismo?",
            "¿Como estara el clima el 20 de octubre?",
        ],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )

    booking_skill = AgentSkill(
        id="safety_and_booking",
        name="Evaluacion y reservas",
        description=(
            "Evalua si las condiciones meteorologicas son seguras "
            "para realizar la actividad y gestiona solicitudes de reserva."
        ),
        tags=[
            "seguridad",
            "reservas",
            "clima",
        ],
        examples=[
            "¿Es seguro saltar el 20 de octubre?",
            "Quiero reservar para el 20 de octubre.",
        ],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )

    capabilities = AgentCapabilities(
        streaming=False,
        push_notifications=False,
        extended_agent_card=False,
    )

    interface = AgentInterface(
        url=A2A_URL,
        protocol_binding="JSONRPC",
        protocol_version="1.0",
    )

    return AgentCard(
        name="Parachute Assistant",
        description=(
            "Asistente multiagente para consultas, clima, evaluacion "
            "de seguridad y reservas de actividades de paracaidismo."
        ),
        version="1.0.0",
        supported_interfaces=[interface],
        capabilities=capabilities,
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            information_skill,
            booking_skill,
        ],
    )


AGENT_CARD = create_agent_card()