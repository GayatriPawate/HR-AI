import msal
from config.settings import get_settings

settings = get_settings()

_token_cache: dict = {}

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


async def get_graph_token() -> str:
    """Acquire MS Graph token using client credentials flow."""
    if not all([settings.azure_tenant_id, settings.azure_client_id, settings.azure_client_secret]):
        raise RuntimeError(
            "MS Graph not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET in .env"
        )

    app = msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
    )

    result = app.acquire_token_silent(GRAPH_SCOPES, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"Failed to acquire MS Graph token: {error}")

    return result["access_token"]
