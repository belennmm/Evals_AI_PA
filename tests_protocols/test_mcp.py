"""Contrato MCP por Streamable HTTP; no ejecuta cuerpos de herramientas."""
import asyncio


EXPECTED_SCHEMAS = {
    "consultar_faq": {"pregunta": "string"},
    "consultar_clima": {"fecha": "string"},
    "evaluar_condiciones": {
        "fecha": "string",
        "temperatura_2m": "number",
        "precipitacion": "number",
        "cobertura_nubes": "number",
        "velocidad_viento": "number",
        "rachas_viento": "number",
    },
    "crear_reserva": {"fecha": "string", "seguridad_json": "string"},
}


def test_streamable_http_initialization_and_catalog(mcp_url):
    from agents.mcp import MCPServerStreamableHttp

    async def check():
        # __aenter__ conecta e inicializa MCP, no es solamente una peticion GET.
        async with MCPServerStreamableHttp(
            params={"url": mcp_url}, client_session_timeout_seconds=60,
        ) as client:
            assert client.session is not None
            tools = await client.list_tools()
            assert len(tools) == 4
            assert {tool.name for tool in tools} == set(EXPECTED_SCHEMAS)
            for tool in tools:
                schema = tool.model_dump(by_alias=True)["inputSchema"]
                expected = EXPECTED_SCHEMAS[tool.name]
                assert schema["type"] == "object"
                assert set(schema["properties"]) == set(expected)
                assert set(schema["required"]) == set(expected)
                assert {name: value["type"] for name, value in schema["properties"].items()} == expected
            print("MCP inicializado; herramientas=" + ", ".join(sorted(tool.name for tool in tools)))

    asyncio.run(check())
