from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
from app.auth_store import create_pending_login, exchange_device_code_for_session

LOGIN_URL_BASE = "http://127.0.0.1:8000/device"


async def auth_start_handler(arguments: dict) -> list[TextContent]:
    pending = create_pending_login(ttl_minutes=30)

    return [
        TextContent(
            type="text",
            text=(
                "LOGIN_REQUIRED\n"
                f"login_url={LOGIN_URL_BASE}\n"
                f"user_code={pending.user_code}\n"
                f"device_code={pending.device_code}\n"
                "Open login_url and enter user_code."
            )
        )
    ]


async def auth_status_handler(arguments: dict) -> list[TextContent]:
    device_code = (arguments or {}).get("device_code")
    if not device_code:
        return [TextContent(type="text", text="ERROR missing device_code")]

    session = exchange_device_code_for_session(device_code=device_code)

    if not session:
        return [TextContent(type="text", text="PENDING")]

    return [
        TextContent(
            type="text",
            text=f"OK session_id={session.session_id} role={session.role} user_id={session.user_id}"
        )
    ]


AUTH_TOOLS = [
    ToolDef(
        tool=Tool(
            name="auth_start",
            description="Start device login flow.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        handler=auth_start_handler,
    ),
    ToolDef(
        tool=Tool(
            name="auth_status",
            description="Check status of device login.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_code": {
                        "type": "string",
                        "description": "Device code returned by auth_start",
                    }
                },
                "required": ["device_code"],
            },
        ),
        handler=auth_status_handler,
    ),
]
